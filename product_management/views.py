import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.db.models import Q
from github.models import GitHubConnection, GitHubRepository
from .models import (
    Project, WorkflowStep, Vision, Initiative,
    Portfolio, Product, Feature, ProductStep
)
from .ai_service import ProductDiscoveryAI
import requests

logger = logging.getLogger(__name__)


@login_required
def index(request):
    """Main product management dashboard."""
    projects = Project.objects.filter(user=request.user)

    # Check if user has GitHub connection
    try:
        github_connection = request.user.github_connection
        has_github = True
    except GitHubConnection.DoesNotExist:
        github_connection = None
        has_github = False

    context = {
        'projects': projects,
        'has_github': has_github,
    }
    return render(request, 'product_management/index.html', context)


@login_required
@require_POST
def create_project(request):
    """Create a new project."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        repo_id = data.get('repo_id')

        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Project name is required.'
            }, status=400)

        # Get repository if provided
        repository = None
        if repo_id:
            try:
                repository = GitHubRepository.objects.get(
                    id=repo_id,
                    connection__user=request.user
                )
            except GitHubRepository.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Repository not found.'
                }, status=404)

        # Create project
        project = Project.objects.create(
            name=name,
            description=description,
            user=request.user,
            github_repository=repository
        )

        return JsonResponse({
            'success': True,
            'project_id': project.id,
            'message': 'Project created successfully!'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def create_github_repo(request):
    """Create a new GitHub repository."""
    try:
        github_connection = request.user.github_connection
    except GitHubConnection.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'GitHub account not connected.'
        }, status=400)

    try:
        data = json.loads(request.body)
        repo_name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        is_private = data.get('private', False)

        if not repo_name:
            return JsonResponse({
                'success': False,
                'error': 'Repository name is required.'
            }, status=400)

        # Create repository via GitHub API
        api_url = 'https://api.github.com/user/repos'
        headers = {
            'Authorization': f'Bearer {github_connection.access_token}',
            'Accept': 'application/json',
        }
        payload = {
            'name': repo_name,
            'description': description,
            'private': is_private,
            'auto_init': True,  # Initialize with README
        }

        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        repo_data = response.json()

        # Save to database
        from datetime import datetime
        from django.utils import timezone

        created_at = datetime.strptime(repo_data['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        updated_at = datetime.strptime(repo_data['updated_at'], '%Y-%m-%dT%H:%M:%SZ')
        created_at = timezone.make_aware(created_at, timezone.utc)
        updated_at = timezone.make_aware(updated_at, timezone.utc)

        repository = GitHubRepository.objects.create(
            connection=github_connection,
            repo_id=str(repo_data['id']),
            name=repo_data['name'],
            full_name=repo_data['full_name'],
            description=repo_data.get('description', ''),
            html_url=repo_data['html_url'],
            clone_url=repo_data['clone_url'],
            ssh_url=repo_data['ssh_url'],
            private=repo_data['private'],
            fork=repo_data['fork'],
            language=repo_data.get('language', ''),
            default_branch=repo_data.get('default_branch', 'main'),
            created_at=created_at,
            updated_at=updated_at,
        )

        return JsonResponse({
            'success': True,
            'repo_id': repository.id,
            'repo_name': repository.full_name,
            'html_url': repository.html_url,
            'message': 'Repository created successfully!'
        })

    except requests.RequestException as e:
        logger.error(f"GitHub API error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error creating repository: {str(e)}'
        }, status=500)
    except Exception as e:
        logger.error(f"Error creating GitHub repo: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def project_detail(request, project_id):
    """View project details and workflow."""
    project = get_object_or_404(Project, id=project_id, user=request.user)

    # Get all workflow steps for this project
    workflow_steps = WorkflowStep.objects.filter(project=project).select_related(
        'parent_step'
    ).prefetch_related('child_steps')

    # Organize by step type
    steps_by_type = {
        'vision': workflow_steps.filter(step_type='vision'),
        'initiative': workflow_steps.filter(step_type='initiative'),
        'portfolio': workflow_steps.filter(step_type='portfolio'),
        'product': workflow_steps.filter(step_type='product'),
        'feature': workflow_steps.filter(step_type='feature'),
    }

    context = {
        'project': project,
        'steps_by_type': steps_by_type,
        'workflow_steps': workflow_steps,
    }
    return render(request, 'product_management/project_detail.html', context)


@login_required
@require_POST
def create_workflow_step(request, project_id):
    """Create a new workflow step."""
    project = get_object_or_404(Project, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        step_type = data.get('step_type')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        parent_step_id = data.get('parent_step_id')

        if not step_type or not title:
            return JsonResponse({
                'success': False,
                'error': 'Step type and title are required.'
            }, status=400)

        # Validate step type
        valid_steps = ['vision', 'initiative', 'portfolio', 'product', 'feature']
        if step_type not in valid_steps:
            return JsonResponse({
                'success': False,
                'error': 'Invalid step type.'
            }, status=400)

        # Get parent step if provided
        parent_step = None
        if parent_step_id:
            try:
                parent_step = WorkflowStep.objects.get(
                    id=parent_step_id,
                    project=project
                )
            except WorkflowStep.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Parent step not found.'
                }, status=404)

        # Create workflow step
        workflow_step = WorkflowStep.objects.create(
            project=project,
            step_type=step_type,
            title=title,
            description=description,
            parent_step=parent_step
        )

        # Create the specific detail model
        if step_type == 'vision':
            Vision.objects.create(workflow_step=workflow_step)
        elif step_type == 'initiative':
            Initiative.objects.create(workflow_step=workflow_step)
        elif step_type == 'portfolio':
            Portfolio.objects.create(workflow_step=workflow_step)
        elif step_type == 'product':
            Product.objects.create(workflow_step=workflow_step)
        elif step_type == 'feature':
            Feature.objects.create(workflow_step=workflow_step)

        return JsonResponse({
            'success': True,
            'step_id': workflow_step.id,
            'message': f'{step_type.capitalize()} created successfully!'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating workflow step: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def workflow_chat(request, step_id):
    """Chat interface for AI-assisted workflow step."""
    workflow_step = get_object_or_404(
        WorkflowStep,
        id=step_id,
        project__user=request.user
    )

    # Serialize conversation history to JSON for JavaScript
    conversation_json = json.dumps(workflow_step.conversation_history or [])

    context = {
        'workflow_step': workflow_step,
        'project': workflow_step.project,
        'conversation_json': conversation_json,
    }
    return render(request, 'product_management/workflow_chat.html', context)


@login_required
@require_POST
def send_message(request, step_id):
    """Send a message to the AI assistant with streaming support."""
    workflow_step = get_object_or_404(
        WorkflowStep,
        id=step_id,
        project__user=request.user
    )

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        use_streaming = data.get('stream', True)  # Default to streaming

        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty.'
            }, status=400)

        # Use AI service to process message
        ai_service = ProductDiscoveryAI(workflow_step)

        if use_streaming:
            # Return streaming response
            from django.http import StreamingHttpResponse
            response = StreamingHttpResponse(
                ai_service.send_message_stream(message),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
        else:
            # Return regular JSON response (backward compatibility)
            result = ai_service.send_message(message)
            return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_conversation(request, step_id):
    """Get the conversation history for a workflow step."""
    workflow_step = get_object_or_404(
        WorkflowStep,
        id=step_id,
        project__user=request.user
    )

    return JsonResponse({
        'success': True,
        'conversation': workflow_step.conversation_history,
        'readme_content': workflow_step.readme_content,
        'is_completed': workflow_step.is_completed,
    })


@login_required
@require_POST
def generate_readme(request, step_id):
    """Generate README from conversation history."""
    workflow_step = get_object_or_404(
        WorkflowStep,
        id=step_id,
        project__user=request.user
    )

    try:
        ai_service = ProductDiscoveryAI(workflow_step)
        result = ai_service.generate_readme()

        if result['success']:
            # If project has GitHub repo, optionally save it
            # Check both POST data and query parameters
            save_to_github = (
                request.POST.get('save_to_github', 'false') == 'true' or
                request.GET.get('save_to_github', 'false') == 'true'
            )

            if save_to_github and workflow_step.project.github_repository:
                try:
                    github_connection = request.user.github_connection
                    github_result = ai_service.save_readme_to_github(
                        github_connection,
                        workflow_step.project.github_repository
                    )
                    if github_result['success']:
                        result['github_url'] = github_result['url']
                        result['github_file_path'] = github_result['file_path']
                        result['message'] = 'README generated and saved to GitHub!'
                    else:
                        result['github_error'] = github_result.get('error', 'Unknown error')
                        result['message'] = 'README generated but failed to save to GitHub'
                except Exception as e:
                    logger.error(f"Error saving to GitHub: {str(e)}")
                    result['github_error'] = str(e)
                    result['message'] = 'README generated but failed to save to GitHub'

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error generating README: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def complete_step(request, step_id):
    """Mark a workflow step as completed."""
    workflow_step = get_object_or_404(
        WorkflowStep,
        id=step_id,
        project__user=request.user
    )

    workflow_step.is_completed = True
    workflow_step.save()

    return JsonResponse({
        'success': True,
        'message': 'Step marked as completed!'
    })


@login_required
def get_repositories(request):
    """Get list of GitHub repositories for the user."""
    try:
        github_connection = request.user.github_connection
        repositories = github_connection.repositories.all()

        repos_data = [{
            'id': repo.id,
            'name': repo.name,
            'full_name': repo.full_name,
            'description': repo.description,
            'html_url': repo.html_url,
            'private': repo.private,
        } for repo in repositories]

        return JsonResponse({
            'success': True,
            'repositories': repos_data
        })

    except GitHubConnection.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'GitHub not connected.',
            'repositories': []
        })


@login_required
def product_steps(request, step_id):
    """View product steps for a product."""
    workflow_step = get_object_or_404(
        WorkflowStep,
        id=step_id,
        step_type='product',
        project__user=request.user
    )

    try:
        product = workflow_step.product_details
    except Product.DoesNotExist:
        messages.error(request, 'Product details not found.')
        return redirect('product_management:project_detail', project_id=workflow_step.project.id)

    # Get all product steps for this product, ordered by layer and order
    product_steps = ProductStep.objects.filter(product=product).order_by('order', 'created_at')

    # Organize by layer
    steps_by_layer = {
        'strategic': product_steps.filter(layer='strategic'),
        'tactical': product_steps.filter(layer='tactical'),
        'release': product_steps.filter(layer='release'),
    }

    context = {
        'workflow_step': workflow_step,
        'product': product,
        'project': workflow_step.project,
        'product_steps': product_steps,
        'steps_by_layer': steps_by_layer,
    }
    return render(request, 'product_management/product_steps.html', context)


@login_required
@require_POST
def create_product_step(request, step_id):
    """Create a new product step."""
    workflow_step = get_object_or_404(
        WorkflowStep,
        id=step_id,
        step_type='product',
        project__user=request.user
    )

    try:
        product = workflow_step.product_details
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Product not found.'
        }, status=404)

    try:
        data = json.loads(request.body)
        step_type = data.get('step_type')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        layer = data.get('layer')

        if not step_type or not title or not layer:
            return JsonResponse({
                'success': False,
                'error': 'Step type, title, and layer are required.'
            }, status=400)

        # Get the next order number
        max_order = ProductStep.objects.filter(product=product).aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0

        # Create product step
        product_step = ProductStep.objects.create(
            product=product,
            step_type=step_type,
            layer=layer,
            title=title,
            description=description,
            order=max_order + 1
        )

        return JsonResponse({
            'success': True,
            'step_id': product_step.id,
            'message': f'{product_step.get_step_type_display()} created successfully!'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating product step: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def product_step_chat(request, product_step_id):
    """Chat interface for AI-assisted product step."""
    product_step = get_object_or_404(
        ProductStep,
        id=product_step_id,
        product__workflow_step__project__user=request.user
    )

    # Serialize conversation history to JSON for JavaScript
    conversation_json = json.dumps(product_step.conversation_history or [])

    context = {
        'product_step': product_step,
        'product': product_step.product,
        'workflow_step': product_step.product.workflow_step,
        'project': product_step.product.workflow_step.project,
        'conversation_json': conversation_json,
    }
    return render(request, 'product_management/product_step_chat.html', context)


@login_required
@require_POST
def send_product_step_message(request, product_step_id):
    """Send a message to the AI assistant for a product step with streaming support."""
    product_step = get_object_or_404(
        ProductStep,
        id=product_step_id,
        product__workflow_step__project__user=request.user
    )

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        use_streaming = data.get('stream', True)

        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty.'
            }, status=400)

        # Use AI service to process message
        ai_service = ProductDiscoveryAI(product_step)

        if use_streaming:
            # Return streaming response
            from django.http import StreamingHttpResponse
            response = StreamingHttpResponse(
                ai_service.send_message_stream(message),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
        else:
            # Return regular JSON response
            result = ai_service.send_message(message)
            return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_product_step_conversation(request, product_step_id):
    """Get the conversation history for a product step."""
    product_step = get_object_or_404(
        ProductStep,
        id=product_step_id,
        product__workflow_step__project__user=request.user
    )

    return JsonResponse({
        'success': True,
        'conversation': product_step.conversation_history,
        'document_content': product_step.document_content,
        'is_completed': product_step.is_completed,
    })


@login_required
@require_POST
def generate_product_step_document(request, product_step_id):
    """Generate document from conversation history for a product step."""
    product_step = get_object_or_404(
        ProductStep,
        id=product_step_id,
        product__workflow_step__project__user=request.user
    )

    try:
        ai_service = ProductDiscoveryAI(product_step)
        result = ai_service.generate_readme()

        if result['success']:
            # If project has GitHub repo, optionally save it
            save_to_github = (
                request.POST.get('save_to_github', 'false') == 'true' or
                request.GET.get('save_to_github', 'false') == 'true'
            )

            if save_to_github and product_step.product.workflow_step.project.github_repository:
                try:
                    github_connection = request.user.github_connection
                    github_result = ai_service.save_readme_to_github(
                        github_connection,
                        product_step.product.workflow_step.project.github_repository
                    )
                    if github_result['success']:
                        result['github_url'] = github_result['url']
                        result['github_file_path'] = github_result['file_path']
                        result['message'] = 'Document generated and saved to GitHub!'
                    else:
                        result['github_error'] = github_result.get('error', 'Unknown error')
                        result['message'] = 'Document generated but failed to save to GitHub'
                except Exception as e:
                    logger.error(f"Error saving to GitHub: {str(e)}")
                    result['github_error'] = str(e)
                    result['message'] = 'Document generated but failed to save to GitHub'

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error generating document: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def complete_product_step(request, product_step_id):
    """Mark a product step as completed."""
    product_step = get_object_or_404(
        ProductStep,
        id=product_step_id,
        product__workflow_step__project__user=request.user
    )

    product_step.is_completed = True
    product_step.save()

    return JsonResponse({
        'success': True,
        'message': 'Step marked as completed!'
    })
