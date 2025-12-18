import json
import logging
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.db.models import Q
from django.utils import timezone
from github.models import GitHubConnection, GitHubRepository
from .models import (
    Project, WorkflowStep, Vision, Initiative,
    Portfolio, Product, Feature, ProductStep, FeatureStep, RecentItem,
    WorkflowComment, WorkflowActionLog
)
from .ai_service import ProductDiscoveryAI
import requests

logger = logging.getLogger(__name__)


def _serialize_workflow_comment(comment, current_user=None):
    """Serialize a workflow comment for JSON responses."""
    display_name = _format_user_display(comment.user)
    created = timezone.localtime(comment.created_at)
    return {
        'id': comment.id,
        'user': display_name,
        'content': comment.content,
        'created_at': created.strftime('%b %d, %Y %H:%M'),
        'created_at_iso': created.isoformat(),
        'is_owner': bool(current_user and comment.user_id == current_user.id),
    }


def _format_user_display(user):
    if not user:
        return 'System'
    display_name = (user.get_full_name() or '').strip()
    return display_name or user.username


def _serialize_action_log(action):
    metadata = action.metadata or {}
    display_user = metadata.get('display_user')
    created = timezone.localtime(action.created_at)
    return {
        'id': action.id,
        'action_type': action.action_type,
        'action_label': action.get_action_type_display(),
        'user': display_user or _format_user_display(action.user),
        'description': action.description,
        'created_at': created.strftime('%b %d, %Y %H:%M'),
        'created_at_iso': created.isoformat(),
        'metadata': metadata,
    }


def _serialize_document(document):
    created = timezone.localtime(document.created_at)
    return {
        'id': document.id,
        'title': document.title,
        'document_type': document.document_type,
        'document_label': document.get_document_type_display(),
        'user': _format_user_display(document.created_by),
        'source': document.source,
        'content': document.content,
        'created_at': created.strftime('%b %d, %Y %H:%M'),
        'created_at_iso': created.isoformat(),
    }


@login_required
def index(request):
    """Main product management dashboard."""
    projects = Project.objects.filter(user=request.user)

    # Get all products - both project-associated and standalone (owned by user)
    products_query = Product.objects.filter(
        Q(workflow_step__project__user=request.user) | Q(workflow_step__user=request.user)
    ).select_related(
        'workflow_step',
        'workflow_step__project'
    ).prefetch_related('repositories').distinct()

    # Get all features - both project-associated and standalone (owned by user)
    features_query = Feature.objects.filter(
        Q(workflow_step__project__user=request.user) | Q(workflow_step__user=request.user)
    ).select_related(
        'workflow_step',
        'workflow_step__project',
        'workflow_step__parent_step',
        'repository'
    ).distinct()

    # Group products and features by status
    items_by_status = {
        'backlog': {'products': [], 'features': []},
        'todo': {'products': [], 'features': []},
        'in_progress': {'products': [], 'features': []},
        'completed': {'products': [], 'features': []},
    }

    product_repo_map = {}
    for product in products_query:
        status = product.workflow_step.status
        items_by_status[status]['products'].append(product)
        repo_payload = [{
            'id': repo.id,
            'name': repo.name,
            'full_name': repo.full_name,
            'description': repo.description or '',
            'html_url': repo.html_url,
        } for repo in product.repositories.all()]
        product_repo_map[str(product.workflow_step.id)] = repo_payload

    for feature in features_query:
        status = feature.workflow_step.status
        items_by_status[status]['features'].append(feature)

    # Get recent items for quick access (limit to 5 most recent)
    recent_items = RecentItem.objects.filter(user=request.user)[:5]

    # Check if user has GitHub connection
    try:
        github_connection = request.user.github_connection
        has_github = True
    except GitHubConnection.DoesNotExist:
        github_connection = None
        has_github = False

    context = {
        'projects': projects,
        'items_by_status': items_by_status,
        'recent_items': recent_items,
        'has_github': has_github,
        'product_repo_map_json': json.dumps(product_repo_map),
    }
    return render(request, 'product_management/index.html', context)


@login_required
def hierarchy_view(request):
    """Hierarchical tree view of all workflow items."""
    projects = Project.objects.filter(user=request.user).prefetch_related(
        'workflow_steps',
        'workflow_steps__child_steps',
    )

    # Build hierarchy for each project organized by levels
    hierarchy_data = []
    for project in projects:
        # Organize steps by type/level
        visions = project.workflow_steps.filter(step_type='vision')
        initiatives = project.workflow_steps.filter(step_type='initiative')
        portfolios = project.workflow_steps.filter(step_type='portfolio')
        products = project.workflow_steps.filter(step_type='product')

        # Build product -> features mapping
        products_with_features = []
        for product in products:
            features = product.child_steps.filter(step_type='feature')
            products_with_features.append({
                'product': product,
                'features': features
            })

        project_data = {
            'project': project,
            'visions': visions,
            'initiatives': initiatives,
            'portfolios': portfolios,
            'products_with_features': products_with_features,
        }
        hierarchy_data.append(project_data)

    context = {
        'hierarchy_data': hierarchy_data,
    }
    return render(request, 'product_management/hierarchy.html', context)


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
def create_workflow_step(request, project_id=None):
    """Create a new workflow step (with or without project)."""
    # Get project if provided
    project = None
    if project_id:
        project = get_object_or_404(Project, id=project_id, user=request.user)

    try:
        data = json.loads(request.body)
        step_type = data.get('step_type')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        parent_step_id = data.get('parent_step_id')
        provided_project_id = data.get('project_id')
        status = data.get('status', 'backlog')  # Get status from request, default to backlog
        repository_ids_raw = data.get('repository_ids')
        feature_repository_id = data.get('feature_repository_id')

        repository_ids = []
        if repository_ids_raw is not None:
            if not isinstance(repository_ids_raw, list):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid repository selection.'
                }, status=400)
            try:
                repository_ids = [
                    int(repo_id)
                    for repo_id in repository_ids_raw
                    if str(repo_id).strip()
                ]
            except (TypeError, ValueError):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid repository selection.'
                }, status=400)

        # Use provided project_id if no URL project_id
        if not project and provided_project_id:
            try:
                project = Project.objects.get(id=provided_project_id, user=request.user)
            except Project.DoesNotExist:
                pass

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
                # Query for parent step - it may or may not have a project
                parent_step = WorkflowStep.objects.get(id=parent_step_id)
                # Verify user has access (either through project or verify it's accessible)
                if parent_step.project and parent_step.project.user != request.user:
                    return JsonResponse({
                        'success': False,
                        'error': 'Parent step not found.'
                    }, status=404)
                # If parent has project but we don't, inherit it
                if not project and parent_step.project:
                    project = parent_step.project
            except WorkflowStep.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Parent step not found.'
                }, status=404)

        # Validate hierarchy rules
        hierarchy_order = {
            'vision': 0,
            'initiative': 1,
            'portfolio': 2,
            'product': 3,
            'feature': 4
        }

        # Features MUST have a Product as parent
        product_details = None
        selected_feature_repository = None
        if step_type == 'feature':
            if not parent_step:
                return JsonResponse({
                    'success': False,
                    'error': 'Features must be associated with a Product.'
                }, status=400)
            if parent_step.step_type != 'product':
                return JsonResponse({
                    'success': False,
                    'error': 'Features can only be created under a Product.'
                }, status=400)
            try:
                product_details = parent_step.product_details
            except Product.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Parent product details not found.'
                }, status=400)

        # Validate parent-child hierarchy order
        if parent_step:
            parent_level = hierarchy_order.get(parent_step.step_type, -1)
            child_level = hierarchy_order.get(step_type, -1)

            # Child must be exactly one level below parent OR feature under product
            if step_type == 'feature' and parent_step.step_type == 'product':
                # This is valid: Product -> Feature
                pass
            elif child_level != parent_level + 1:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid hierarchy: {step_type.capitalize()} cannot be a child of {parent_step.step_type.capitalize()}. '
                            f'Valid hierarchy: Vision → Initiative → Portfolio → Product → Feature'
                }, status=400)

        # Prepare repository selections (only for products)
        selected_repositories = []
        if step_type == 'product':
            if not repository_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'Select at least one repository for a product.'
                }, status=400)
            try:
                github_connection = request.user.github_connection
            except GitHubConnection.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Connect your GitHub account before linking repositories.'
                }, status=400)

            unique_repo_ids = []
            seen_repo_ids = set()
            for repo_id in repository_ids:
                if repo_id not in seen_repo_ids:
                    unique_repo_ids.append(repo_id)
                    seen_repo_ids.add(repo_id)

            selected_repositories = list(GitHubRepository.objects.filter(
                id__in=unique_repo_ids,
                connection=github_connection
            ))
            if len(selected_repositories) != len(unique_repo_ids):
                return JsonResponse({
                    'success': False,
                    'error': 'One or more repositories could not be found.'
                }, status=400)

        # Create workflow step
        workflow_step = WorkflowStep.objects.create(
            project=project,  # Can be None for standalone steps
            user=request.user if not project else None,  # Set user for standalone steps
            step_type=step_type,
            title=title,
            description=description,
            parent_step=parent_step,
            status=status  # Set the status from request
        )

        # Create the specific detail model
        if step_type == 'vision':
            Vision.objects.create(workflow_step=workflow_step)
        elif step_type == 'initiative':
            Initiative.objects.create(workflow_step=workflow_step)
        elif step_type == 'portfolio':
            Portfolio.objects.create(workflow_step=workflow_step)
        elif step_type == 'product':
            product = Product.objects.create(workflow_step=workflow_step)
            if selected_repositories:
                product.repositories.set(selected_repositories)
        elif step_type == 'feature':
            if not feature_repository_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Select a repository to use for this feature.'
                }, status=400)
            try:
                feature_repository_id = int(feature_repository_id)
            except (TypeError, ValueError):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid repository selection.'
                }, status=400)
            if not product_details:
                return JsonResponse({
                    'success': False,
                    'error': 'Unable to determine product repositories.'
                }, status=400)
            selected_feature_repository = product_details.repositories.filter(id=feature_repository_id).first()
            if not selected_feature_repository:
                return JsonResponse({
                    'success': False,
                    'error': 'Selected repository is not linked to the parent product.'
                }, status=400)
            Feature.objects.create(
                workflow_step=workflow_step,
                repository=selected_feature_repository
            )

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
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            from django.http import Http404
            raise Http404("Workflow step not found.")
    elif workflow_step.user and workflow_step.user != request.user:
        from django.http import Http404
        raise Http404("Workflow step not found.")

    # Build hierarchy breadcrumbs
    hierarchy = []
    current = workflow_step
    while current:
        hierarchy.insert(0, current)
        current = current.parent_step

    # Serialize conversation history to JSON for JavaScript
    conversation_json = json.dumps(workflow_step.conversation_history or [])
    recent_comments = list(
        workflow_step.comments.select_related('user').order_by('-created_at')[:50]
    )
    serialized_comments = [
        _serialize_workflow_comment(comment, request.user)
        for comment in reversed(recent_comments)
    ]
    action_logs = workflow_step.action_logs.select_related('user').order_by('-created_at')[:50]
    serialized_actions = [_serialize_action_log(action) for action in action_logs]
    documents = list(
        workflow_step.documents.select_related('created_by').order_by('-created_at')
    )
    serialized_documents = [
        _serialize_document(doc)
        for doc in documents
    ]

    product_details = None
    product_repositories = []
    if workflow_step.step_type == 'product':
        try:
            product_details = workflow_step.product_details
            product_repositories = list(product_details.repositories.all())
        except Product.DoesNotExist:
            product_details = None

    feature_details = None
    feature_repository = None
    if workflow_step.step_type == 'feature':
        try:
            feature_details = workflow_step.feature_details
            feature_repository = feature_details.repository
        except Feature.DoesNotExist:
            feature_details = None

    repository_for_actions = None
    if workflow_step.step_type == 'feature':
        repository_for_actions = feature_repository
    elif workflow_step.project:
        repository_for_actions = workflow_step.project.github_repository

    context = {
        'workflow_step': workflow_step,
        'project': workflow_step.project,
        'hierarchy': hierarchy,
        'conversation_json': conversation_json,
        'comments_json': json.dumps(serialized_comments),
        'comment_count': workflow_step.comments.count(),
        'actions_json': json.dumps(serialized_actions),
        'documents_json': json.dumps(serialized_documents),
        'document_count': len(serialized_documents),
        'product_details': product_details,
        'product_repositories': product_repositories,
        'feature_details': feature_details,
        'feature_repository': feature_repository,
        'repository_for_actions': repository_for_actions,
    }
    return render(request, 'product_management/workflow_chat.html', context)


@login_required
@require_POST
def send_message(request, step_id):
    """Send a message to the AI assistant with streaming support."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Workflow step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Workflow step not found.'
        }, status=404)

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
def workflow_comments(request, step_id):
    """Handle listing and creating comments for a workflow step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify access
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)

    if request.method == 'GET':
        comments = workflow_step.comments.select_related('user').order_by('-created_at')[:50]
        serialized = [
            _serialize_workflow_comment(comment, request.user)
            for comment in reversed(list(comments))
        ]
        return JsonResponse({
            'success': True,
            'comments': serialized,
            'count': workflow_step.comments.count()
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)

        content = (data.get('content') or '').strip()
        if not content:
            return JsonResponse({'success': False, 'error': 'Comment cannot be empty.'}, status=400)

        comment = WorkflowComment.objects.create(
            workflow_step=workflow_step,
            user=request.user,
            content=content
        )
        workflow_step.log_action(
            'comment_added',
            request.user,
            description=f'Comment added: {content[:100]}',
            metadata={'comment_id': comment.id}
        )
        return JsonResponse({
            'success': True,
            'comment': _serialize_workflow_comment(comment, request.user),
            'count': workflow_step.comments.count()
        })

    return JsonResponse({'success': False, 'error': 'Method not allowed.'}, status=405)


@login_required
def workflow_actions(request, step_id):
    """Return recent action logs for a workflow step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)

    actions = workflow_step.action_logs.select_related('user').order_by('-created_at')[:100]
    serialized = [_serialize_action_log(action) for action in actions]
    return JsonResponse({'success': True, 'actions': serialized})


@login_required
def workflow_documents(request, step_id):
    """Return generated documents for a workflow step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)

    documents = workflow_step.documents.select_related('created_by').order_by('-created_at')
    serialized = [_serialize_document(doc) for doc in documents]
    return JsonResponse({'success': True, 'documents': serialized})


@login_required
@require_POST
def create_workflow_action(request, step_id):
    """Allow clients to add custom action log entries (e.g., AI events)."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({'success': False, 'error': 'Workflow step not found.'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)

    action_type = data.get('action_type')
    description = (data.get('description') or '').strip()
    metadata = data.get('metadata') or {}
    display_user = data.get('display_user')
    as_system = data.get('as_system', False)

    if not isinstance(metadata, dict):
        metadata = {}

    valid_action_types = {choice[0] for choice in WorkflowActionLog.ACTION_CHOICES}
    if action_type not in valid_action_types:
        return JsonResponse({'success': False, 'error': 'Invalid action type.'}, status=400)

    if display_user:
        metadata = dict(metadata)
        metadata['display_user'] = display_user

    log_entry = workflow_step.log_action(
        action_type=action_type,
        user=None if as_system else request.user,
        description=description,
        metadata=metadata
    )

    return JsonResponse({
        'success': True,
        'action': _serialize_action_log(log_entry)
    })


@login_required
def get_conversation(request, step_id):
    """Get the conversation history for a workflow step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Workflow step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Workflow step not found.'
        }, status=404)

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
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Workflow step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Workflow step not found.'
        }, status=404)

    try:
        # Set status to in_progress when generating README
        workflow_step.status = 'in_progress'
        workflow_step.save()

        ai_service = ProductDiscoveryAI(workflow_step)
        result = ai_service.generate_readme()
        document_entry = None

        if result['success']:
            readme_content = result.get('readme_content') or workflow_step.readme_content
            if readme_content:
                document_entry = workflow_step.save_document_version(
                    title=f"README - {timezone.localtime(timezone.now()).strftime('%b %d, %Y %H:%M')}",
                    content=readme_content,
                    document_type='readme',
                    user=request.user,
                    source='ai'
                )
                workflow_step.log_action(
                    'readme_generated',
                    request.user,
                    description=document_entry.title,
                    metadata={'document_id': document_entry.id}
                )
                result['document'] = _serialize_document(document_entry)

            # If project has GitHub repo, optionally save it
            # Check both POST data and query parameters
            save_to_github = (
                request.POST.get('save_to_github', 'false') == 'true' or
                request.GET.get('save_to_github', 'false') == 'true'
            )

            target_repository = None
            if workflow_step.step_type == 'feature':
                try:
                    target_repository = workflow_step.feature_details.repository
                except Feature.DoesNotExist:
                    target_repository = None
            elif workflow_step.project:
                target_repository = workflow_step.project.github_repository

            if save_to_github and target_repository:
                try:
                    github_connection = request.user.github_connection
                    github_result = ai_service.save_readme_to_github(
                        github_connection,
                        target_repository
                    )
                    if github_result['success']:
                        result['github_url'] = github_result['url']
                        result['github_file_path'] = github_result['file_path']
                        result['message'] = 'README generated and saved to GitHub!'
                        workflow_step.log_action(
                            'document_saved',
                            request.user,
                            description=f"README pushed to GitHub ({github_result['file_path']})",
                            metadata={
                                'document_id': document_entry.id if document_entry else None,
                                'github_url': github_result['url']
                            }
                        )
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
def ensure_readme_synced(request, step_id):
    """Ensure a feature README exists, is up-to-date, and saved to GitHub."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify user access
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Workflow step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Workflow step not found.'
        }, status=404)

    if workflow_step.step_type != 'feature':
        return JsonResponse({
            'success': False,
            'error': 'Automatic README sync is only available for features.'
        }, status=400)

    try:
        feature_details = workflow_step.feature_details
    except Feature.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Feature details not found.'
        }, status=400)

    feature_repository = feature_details.repository
    if not feature_repository:
        return JsonResponse({
            'success': False,
            'error': 'Link this feature to one of its product repositories before requesting code changes.'
        }, status=400)

    try:
        ai_service = ProductDiscoveryAI(workflow_step)
        document_entry = None

        # Determine if README needs regeneration
        needs_generation = (
            not workflow_step.readme_content or
            not workflow_step.readme_generated_at
        )

        if not needs_generation and workflow_step.updated_at and workflow_step.readme_generated_at:
            delta = workflow_step.updated_at - workflow_step.readme_generated_at
            if delta > timedelta(seconds=1):
                needs_generation = True

        if needs_generation:
            # Mark as in progress to reflect active work
            if workflow_step.status != 'in_progress':
                workflow_step.status = 'in_progress'
                workflow_step.save(update_fields=['status'])

            generate_result = ai_service.generate_readme()
            if not generate_result.get('success'):
                return JsonResponse({
                    'success': False,
                    'error': generate_result.get('error', 'Unable to generate README. Try adding more context first.')
                }, status=400)
            readme_content = generate_result.get('readme_content') or workflow_step.readme_content
            if readme_content:
                document_entry = workflow_step.save_document_version(
                    title=f"README - {timezone.localtime(timezone.now()).strftime('%b %d, %Y %H:%M')}",
                    content=readme_content,
                    document_type='readme',
                    user=request.user,
                    source='ai'
                )
                workflow_step.log_action(
                    'readme_generated',
                    request.user,
                    description=document_entry.title,
                    metadata={'document_id': document_entry.id}
                )

        if not workflow_step.readme_content:
            return JsonResponse({
                'success': False,
                'error': 'README content is empty. Add more detail to the feature before requesting code generation.'
            }, status=400)

        # Save README to GitHub
        try:
            github_connection = request.user.github_connection
        except GitHubConnection.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Connect your GitHub account before requesting code changes.'
            }, status=400)

        github_result = ai_service.save_readme_to_github(
            github_connection,
            feature_repository
        )

        if not github_result.get('success'):
            return JsonResponse({
                'success': False,
                'error': github_result.get('error', 'Failed to save README to GitHub.')
            }, status=400)
        workflow_step.log_action(
            'document_saved',
            request.user,
            description=f"README pushed to GitHub ({github_result.get('file_path')})",
            metadata={
                'document_id': document_entry.id if document_entry else None,
                'github_url': github_result.get('url')
            }
        )

        return JsonResponse({
            'success': True,
            'readme_content': workflow_step.readme_content,
            'regenerated': needs_generation,
            'github_url': github_result.get('url'),
            'github_file_path': github_result.get('file_path'),
            'document': _serialize_document(document_entry) if document_entry else None
        })

    except Exception as e:
        logger.error(f"Error ensuring README sync: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def complete_step(request, step_id):
    """Mark a workflow step as completed."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Workflow step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Workflow step not found.'
        }, status=404)

    workflow_step.is_completed = True
    workflow_step.status = 'completed'  # Set status to completed
    workflow_step.save()
    workflow_step.log_action(
        'step_completed',
        request.user,
        description='Step marked as completed.'
    )

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
    workflow_step = get_object_or_404(WorkflowStep, id=step_id, step_type='product')

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            from django.http import Http404
            raise Http404("Product not found.")
    elif workflow_step.user and workflow_step.user != request.user:
        from django.http import Http404
        raise Http404("Product not found.")

    try:
        product = workflow_step.product_details
    except Product.DoesNotExist:
        messages.error(request, 'Product details not found.')
        if workflow_step.project:
            return redirect('product_management:project_detail', project_id=workflow_step.project.id)
        else:
            return redirect('product_management:index')

    # Build hierarchy breadcrumbs
    hierarchy = []
    current = workflow_step
    while current:
        hierarchy.insert(0, current)
        current = current.parent_step

    # Get all product steps for this product, ordered by layer and order
    product_steps = ProductStep.objects.filter(product=product).order_by('order', 'created_at')

    # Organize by layer
    steps_by_layer = {
        'strategic': product_steps.filter(layer='strategic'),
        'tactical': product_steps.filter(layer='tactical'),
        'release': product_steps.filter(layer='release'),
    }

    product_repositories = list(product.repositories.all())

    context = {
        'workflow_step': workflow_step,
        'product': product,
        'project': workflow_step.project,
        'hierarchy': hierarchy,
        'product_steps': product_steps,
        'steps_by_layer': steps_by_layer,
        'product_repositories': product_repositories,
    }
    return render(request, 'product_management/product_steps.html', context)


@login_required
@require_POST
def create_product_step(request, step_id):
    """Create a new product step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id, step_type='product')

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Product not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Product not found.'
        }, status=404)

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
def feature_steps(request, step_id):
    """View feature steps for a feature."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id, step_type='feature')

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            from django.http import Http404
            raise Http404("Feature not found.")
    elif workflow_step.user and workflow_step.user != request.user:
        from django.http import Http404
        raise Http404("Feature not found.")

    try:
        feature = workflow_step.feature_details
    except Feature.DoesNotExist:
        messages.error(request, 'Feature details not found.')
        if workflow_step.project:
            return redirect('product_management:project_detail', project_id=workflow_step.project.id)
        else:
            return redirect('product_management:index')

    # Build hierarchy breadcrumbs
    hierarchy = []
    current = workflow_step
    while current:
        hierarchy.insert(0, current)
        current = current.parent_step

    # Get all feature steps ordered by layer & order
    feature_steps_qs = FeatureStep.objects.filter(feature=feature).order_by('order', 'created_at')

    planning_steps = list(feature_steps_qs.filter(layer='planning'))
    development_steps = list(feature_steps_qs.filter(layer='development'))
    delivery_steps = list(feature_steps_qs.filter(layer='delivery'))

    steps_by_layer = {
        'planning': planning_steps,
        'development': development_steps,
        'delivery': delivery_steps,
    }
    planning_count = len(planning_steps)
    development_count = len(development_steps)
    delivery_count = len(delivery_steps)

    context = {
        'workflow_step': workflow_step,
        'feature': feature,
        'project': workflow_step.project,
        'hierarchy': hierarchy,
        'feature_steps': feature_steps_qs,
        'steps_by_layer': steps_by_layer,
        'planning_count': planning_count,
        'development_count': development_count,
        'delivery_count': delivery_count,
        'feature_repository': feature.repository,
    }
    return render(request, 'product_management/feature_steps.html', context)


@login_required
@require_POST
def create_feature_step(request, step_id):
    """Create a new feature step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id, step_type='feature')

    # Verify user has access (either through project or standalone with user ownership)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Feature not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Feature not found.'
        }, status=404)

    try:
        feature = workflow_step.feature_details
    except Feature.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Feature not found.'
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
        max_order = FeatureStep.objects.filter(feature=feature).aggregate(
            max_order=models.Max('order')
        )['max_order'] or 0

        feature_step = FeatureStep.objects.create(
            feature=feature,
            step_type=step_type,
            layer=layer,
            title=title,
            description=description,
            order=max_order + 1
        )

        return JsonResponse({
            'success': True,
            'step_id': feature_step.id,
            'message': f'{feature_step.get_step_type_display()} created successfully!'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating feature step: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def track_recent_item(request):
    """Track recently accessed item."""
    try:
        data = json.loads(request.body)
        item_type = data.get('item_type')
        item_id = data.get('item_id')
        item_title = data.get('item_title')
        item_url = data.get('item_url')

        if not all([item_type, item_id, item_title, item_url]):
            return JsonResponse({
                'success': False,
                'error': 'All fields are required.'
            }, status=400)

        # Update or create recent item
        recent_item, created = RecentItem.objects.update_or_create(
            user=request.user,
            item_type=item_type,
            item_id=item_id,
            defaults={
                'item_title': item_title,
                'item_url': item_url,
            }
        )

        return JsonResponse({
            'success': True,
            'message': 'Recent item tracked successfully!'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error tracking recent item: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def update_status(request):
    """Update the status of a workflow step (for Kanban board drag-and-drop)."""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        new_status = data.get('status')

        if not item_id or not new_status:
            return JsonResponse({
                'success': False,
                'error': 'Item ID and status are required.'
            }, status=400)

        # Validate status
        valid_statuses = ['backlog', 'todo', 'in_progress', 'completed']
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)

        # Get the workflow step and verify user has access
        workflow_step = get_object_or_404(WorkflowStep, id=item_id)

        # Check if user has access (either through project or user ownership)
        if workflow_step.project:
            if workflow_step.project.user != request.user:
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have permission to update this item.'
                }, status=403)
        elif workflow_step.user and workflow_step.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to update this item.'
            }, status=403)

        # Update the status
        workflow_step.status = new_status

        # Also update is_completed for backward compatibility
        if new_status == 'completed':
            workflow_step.is_completed = True
        else:
            workflow_step.is_completed = False

        workflow_step.save()

        return JsonResponse({
            'success': True,
            'message': f'Status updated to {new_status}',
            'new_status': new_status
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def update_workflow_step(request, step_id):
    """Update editable fields (e.g., description) for a workflow step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify access rights (project owner or standalone owner)
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to update this item.'
            }, status=403)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'You do not have permission to update this item.'
        }, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)

    description = data.get('description')
    title = data.get('title')

    if description is None and title is None:
        return JsonResponse({
            'success': False,
            'error': 'No updates provided.'
        }, status=400)

    try:
        updated_fields = []
        original_title = workflow_step.title
        original_description = workflow_step.description or ''
        title_changed = False
        description_changed = False

        if title is not None:
            cleaned_title = title.strip()
            if not cleaned_title:
                return JsonResponse({
                    'success': False,
                    'error': 'Title cannot be empty.'
                }, status=400)
            workflow_step.title = cleaned_title
            updated_fields.append('title')
            title_changed = cleaned_title != original_title

        if description is not None:
            cleaned_description = description.strip()
            workflow_step.description = cleaned_description
            updated_fields.append('description')
            description_changed = cleaned_description != original_description

        workflow_step.save()

        if title_changed:
            workflow_step.log_action(
                'title_updated',
                request.user,
                description=f'Title updated to "{workflow_step.title}"'
            )
        if description_changed:
            workflow_step.log_action(
                'description_updated',
                request.user,
                description='Description updated.'
            )

        return JsonResponse({
            'success': True,
            'message': 'Workflow step updated successfully.',
            'title': workflow_step.title,
            'description': workflow_step.description
        })
    except Exception as e:
        logger.error(f"Error updating workflow step: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def product_step_chat(request, product_step_id):
    """Chat interface for AI-assisted product step."""
    product_step = get_object_or_404(ProductStep, id=product_step_id)

    # Verify user has access (either through project or standalone with user ownership)
    workflow_step = product_step.product.workflow_step
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            from django.http import Http404
            raise Http404("Product step not found.")
    elif workflow_step.user and workflow_step.user != request.user:
        from django.http import Http404
        raise Http404("Product step not found.")

    # Build hierarchy breadcrumbs
    hierarchy = []
    current = workflow_step
    while current:
        hierarchy.insert(0, current)
        current = current.parent_step

    # Serialize conversation history to JSON for JavaScript
    conversation_json = json.dumps(product_step.conversation_history or [])

    context = {
        'product_step': product_step,
        'product': product_step.product,
        'workflow_step': workflow_step,
        'project': workflow_step.project,
        'hierarchy': hierarchy,
        'conversation_json': conversation_json,
    }
    return render(request, 'product_management/product_step_chat.html', context)


@login_required
@require_POST
def send_product_step_message(request, product_step_id):
    """Send a message to the AI assistant for a product step with streaming support."""
    product_step = get_object_or_404(ProductStep, id=product_step_id)

    # Verify user has access (either through project or standalone with user ownership)
    workflow_step = product_step.product.workflow_step
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Product step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Product step not found.'
        }, status=404)

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
    product_step = get_object_or_404(ProductStep, id=product_step_id)

    # Verify user has access (either through project or standalone with user ownership)
    workflow_step = product_step.product.workflow_step
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Product step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Product step not found.'
        }, status=404)

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
    product_step = get_object_or_404(ProductStep, id=product_step_id)

    # Verify user has access (either through project or standalone with user ownership)
    workflow_step = product_step.product.workflow_step
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Product step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Product step not found.'
        }, status=404)

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
    product_step = get_object_or_404(ProductStep, id=product_step_id)

    # Verify user has access (either through project or standalone with user ownership)
    workflow_step = product_step.product.workflow_step
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Product step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Product step not found.'
        }, status=404)

    product_step.is_completed = True
    product_step.save()

    return JsonResponse({
        'success': True,
        'message': 'Step marked as completed!'
    })


@login_required
@require_POST
def delete_project(request, project_id):
    """Delete a project."""
    project = get_object_or_404(Project, id=project_id, user=request.user)

    try:
        project_name = project.name

        # Delete recent items for this project
        RecentItem.objects.filter(user=request.user, item_type='project', item_id=project_id).delete()

        # Delete recent items for all workflow steps in this project
        workflow_step_ids = project.workflow_steps.values_list('id', flat=True)
        RecentItem.objects.filter(
            user=request.user,
            item_type__in=['product', 'feature', 'workflow'],
            item_id__in=workflow_step_ids
        ).delete()

        project.delete()

        return JsonResponse({
            'success': True,
            'message': f'Project "{project_name}" deleted successfully!'
        })
    except Exception as e:
        logger.error(f"Error deleting project: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def delete_workflow_step(request, step_id):
    """Delete a workflow step."""
    workflow_step = get_object_or_404(WorkflowStep, id=step_id)

    # Verify user has access
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Workflow step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Workflow step not found.'
        }, status=404)

    try:
        step_title = workflow_step.title
        step_type = workflow_step.get_step_type_display()
        project = workflow_step.project

        # Delete recent items for this workflow step (product, feature, or workflow)
        RecentItem.objects.filter(
            user=request.user,
            item_type__in=['product', 'feature', 'workflow'],
            item_id=step_id
        ).delete()

        workflow_step.delete()

        return JsonResponse({
            'success': True,
            'message': f'{step_type} "{step_title}" deleted successfully!',
            'redirect_url': f'/product-management/project/{project.id}/' if project else '/product-management/'
        })
    except Exception as e:
        logger.error(f"Error deleting workflow step: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def delete_product_step(request, product_step_id):
    """Delete a product step."""
    product_step = get_object_or_404(ProductStep, id=product_step_id)

    # Verify user has access
    workflow_step = product_step.product.workflow_step
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Product step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Product step not found.'
        }, status=404)

    try:
        step_title = product_step.title
        product_id = workflow_step.id

        product_step.delete()

        return JsonResponse({
            'success': True,
            'message': f'Product step "{step_title}" deleted successfully!',
            'redirect_url': f'/product-management/product/{product_id}/steps/'
        })
    except Exception as e:
        logger.error(f"Error deleting product step: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def feature_step_chat(request, feature_step_id):
    """Chat interface for AI-assisted feature step."""
    feature_step = get_object_or_404(FeatureStep, id=feature_step_id)

    workflow_step = feature_step.feature.workflow_step

    # Verify user has access
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            from django.http import Http404
            raise Http404("Feature step not found.")
    elif workflow_step.user and workflow_step.user != request.user:
        from django.http import Http404
        raise Http404("Feature step not found.")

    # Build hierarchy breadcrumbs
    hierarchy = []
    current = workflow_step
    while current:
        hierarchy.insert(0, current)
        current = current.parent_step

    conversation_json = json.dumps(feature_step.conversation_history or [])

    context = {
        'feature_step': feature_step,
        'feature': feature_step.feature,
        'workflow_step': workflow_step,
        'project': workflow_step.project,
        'hierarchy': hierarchy,
        'conversation_json': conversation_json,
        'feature_repository': feature_step.feature.repository,
    }
    return render(request, 'product_management/feature_step_chat.html', context)


@login_required
@require_POST
def send_feature_step_message(request, feature_step_id):
    """Send a message to the AI assistant for a feature step."""
    feature_step = get_object_or_404(FeatureStep, id=feature_step_id)
    workflow_step = feature_step.feature.workflow_step

    # Verify user has access
    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Feature step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Feature step not found.'
        }, status=404)

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        use_streaming = data.get('stream', True)

        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty.'
            }, status=400)

        ai_service = ProductDiscoveryAI(feature_step)

        if use_streaming:
            from django.http import StreamingHttpResponse
            response = StreamingHttpResponse(
                ai_service.send_message_stream(message),
                content_type='text/event-stream'
            )
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
        else:
            result = ai_service.send_message(message)
            return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        logger.error(f"Error sending feature step message: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_feature_step_conversation(request, feature_step_id):
    """Get conversation history for a feature step."""
    feature_step = get_object_or_404(FeatureStep, id=feature_step_id)
    workflow_step = feature_step.feature.workflow_step

    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Feature step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Feature step not found.'
        }, status=404)

    return JsonResponse({
        'success': True,
        'conversation': feature_step.conversation_history,
        'document_content': feature_step.document_content,
        'is_completed': feature_step.is_completed,
    })


@login_required
@require_POST
def generate_feature_step_document(request, feature_step_id):
    """Generate document from conversation history for a feature step."""
    feature_step = get_object_or_404(FeatureStep, id=feature_step_id)
    workflow_step = feature_step.feature.workflow_step

    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Feature step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Feature step not found.'
        }, status=404)

    try:
        ai_service = ProductDiscoveryAI(feature_step)
        result = ai_service.generate_readme()

        if result['success']:
            save_to_github = (
                request.POST.get('save_to_github', 'false') == 'true' or
                request.GET.get('save_to_github', 'false') == 'true'
            )

            target_repository = feature_step.feature.repository
            if save_to_github:
                if not target_repository:
                    result['github_error'] = 'Link this feature to a repository before saving to GitHub.'
                    result['message'] = 'Document generated but no repository configured.'
                else:
                    try:
                        github_connection = request.user.github_connection
                        github_result = ai_service.save_readme_to_github(
                            github_connection,
                            target_repository
                        )
                        if github_result['success']:
                            result['github_url'] = github_result['url']
                            result['github_file_path'] = github_result['file_path']
                            result['message'] = 'Document generated and saved to GitHub!'
                        else:
                            result['github_error'] = github_result.get('error', 'Unknown error')
                            result['message'] = 'Document generated but failed to save to GitHub'
                    except Exception as e:
                        logger.error(f"Error saving feature document to GitHub: {str(e)}")
                        result['github_error'] = str(e)
                        result['message'] = 'Document generated but failed to save to GitHub'

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error generating feature document: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def complete_feature_step(request, feature_step_id):
    """Mark a feature step as completed."""
    feature_step = get_object_or_404(FeatureStep, id=feature_step_id)
    workflow_step = feature_step.feature.workflow_step

    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Feature step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Feature step not found.'
        }, status=404)

    feature_step.is_completed = True
    feature_step.save()

    return JsonResponse({
        'success': True,
        'message': 'Step marked as completed!'
    })


@login_required
@require_POST
def delete_feature_step(request, feature_step_id):
    """Delete a feature step."""
    feature_step = get_object_or_404(FeatureStep, id=feature_step_id)
    workflow_step = feature_step.feature.workflow_step

    if workflow_step.project:
        if workflow_step.project.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'Feature step not found.'
            }, status=404)
    elif workflow_step.user and workflow_step.user != request.user:
        return JsonResponse({
            'success': False,
            'error': 'Feature step not found.'
        }, status=404)

    try:
        step_title = feature_step.title
        feature_id = workflow_step.id

        feature_step.delete()

        return JsonResponse({
            'success': True,
            'message': f'Feature step "{step_title}" deleted successfully!',
            'redirect_url': f'/product-management/feature/{feature_id}/steps/'
        })
    except Exception as e:
        logger.error(f"Error deleting feature step: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
