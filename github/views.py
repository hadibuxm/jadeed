import requests
import secrets
import json
import logging
from datetime import datetime
from urllib.parse import urlencode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import GitHubConnection, GitHubRepository, CodeChangeRequest
from .code_change_service import CodeChangeService
import threading

logger = logging.getLogger(__name__)


@login_required
def index(request):
    """Display GitHub connection status and repositories."""
    try:
        github_connection = request.user.github_connection
        has_connection = True
    except GitHubConnection.DoesNotExist:
        github_connection = None
        has_connection = False

    repositories = []
    if github_connection:
        repositories = github_connection.repositories.all()

    context = {
        'has_connection': has_connection,
        'github_connection': github_connection,
        'repositories': repositories,
    }
    return render(request, 'github/index.html', context)


@login_required
def connect(request):
    """Initiate GitHub OAuth flow."""
    # Generate state parameter for security
    state = secrets.token_urlsafe(32)
    request.session['github_oauth_state'] = state

    # Build authorization URL
    params = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'redirect_uri': settings.GITHUB_REDIRECT_URI,
        'scope': settings.GITHUB_SCOPES,
        'state': state,
    }
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return redirect(auth_url)


@login_required
def callback(request):
    """Handle GitHub OAuth callback."""
    # Verify state parameter
    state = request.GET.get('state')
    saved_state = request.session.get('github_oauth_state')

    if not state or state != saved_state:
        messages.error(request, 'Invalid state parameter. Authentication failed.')
        return redirect('github:index')

    # Get authorization code
    code = request.GET.get('code')
    if not code:
        messages.error(request, 'No authorization code received.')
        return redirect('github:index')

    # Exchange code for access token
    token_url = 'https://github.com/login/oauth/access_token'
    token_data = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'client_secret': settings.GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': settings.GITHUB_REDIRECT_URI,
    }
    headers = {'Accept': 'application/json'}

    try:
        response = requests.post(token_url, data=token_data, headers=headers)
        response.raise_for_status()
        token_response = response.json()

        access_token = token_response.get('access_token')
        if not access_token:
            messages.error(request, 'Failed to obtain access token.')
            return redirect('github:index')

        # Get user information from GitHub
        user_url = 'https://api.github.com/user'
        user_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        }
        user_response = requests.get(user_url, headers=user_headers)
        user_response.raise_for_status()
        user_data = user_response.json()

        # Save or update GitHub connection
        github_connection, created = GitHubConnection.objects.update_or_create(
            user=request.user,
            defaults={
                'access_token': access_token,
                'token_type': token_response.get('token_type', 'bearer'),
                'scope': token_response.get('scope', ''),
                'github_user_id': str(user_data.get('id', '')),
                'github_username': user_data.get('login', ''),
                'github_avatar_url': user_data.get('avatar_url', ''),
            }
        )

        if created:
            messages.success(request, f'Successfully connected to GitHub as {user_data.get("login")}!')
        else:
            messages.success(request, f'GitHub connection updated for {user_data.get("login")}!')

        # Clean up session
        del request.session['github_oauth_state']

        return redirect('github:index')

    except requests.RequestException as e:
        messages.error(request, f'Error connecting to GitHub: {str(e)}')
        return redirect('github:index')


@login_required
def disconnect(request):
    """Disconnect GitHub account."""
    if request.method == 'POST':
        try:
            github_connection = request.user.github_connection
            github_connection.delete()
            messages.success(request, 'GitHub account disconnected successfully.')
        except GitHubConnection.DoesNotExist:
            messages.info(request, 'No GitHub connection found.')

    return redirect('github:index')


@login_required
def fetch_repositories(request):
    """Fetch repositories from GitHub API and store them."""
    try:
        github_connection = request.user.github_connection
    except GitHubConnection.DoesNotExist:
        messages.error(request, 'Please connect your GitHub account first.')
        return redirect('github:index')

    # Fetch repositories from GitHub API
    repos_url = 'https://api.github.com/user/repos'
    headers = {
        'Authorization': f'Bearer {github_connection.access_token}',
        'Accept': 'application/json',
    }
    params = {
        'per_page': 100,  # Max per page
        'sort': 'updated',
    }

    try:
        all_repos = []
        page = 1

        while True:
            params['page'] = page
            response = requests.get(repos_url, headers=headers, params=params)
            response.raise_for_status()
            repos = response.json()

            if not repos:
                break

            all_repos.extend(repos)
            page += 1

            # GitHub typically limits to 100 pages
            if page > 100:
                break

        # Save repositories to database
        saved_count = 0
        for repo_data in all_repos:
            # Parse dates
            created_at = datetime.strptime(repo_data['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            updated_at = datetime.strptime(repo_data['updated_at'], '%Y-%m-%dT%H:%M:%SZ')
            pushed_at = None
            if repo_data.get('pushed_at'):
                pushed_at = datetime.strptime(repo_data['pushed_at'], '%Y-%m-%dT%H:%M:%SZ')

            # Make dates timezone-aware
            created_at = timezone.make_aware(created_at, timezone.utc)
            updated_at = timezone.make_aware(updated_at, timezone.utc)
            if pushed_at:
                pushed_at = timezone.make_aware(pushed_at, timezone.utc)

            GitHubRepository.objects.update_or_create(
                connection=github_connection,
                repo_id=str(repo_data['id']),
                defaults={
                    'name': repo_data['name'],
                    'full_name': repo_data['full_name'],
                    'description': repo_data.get('description', ''),
                    'html_url': repo_data['html_url'],
                    'clone_url': repo_data['clone_url'],
                    'ssh_url': repo_data['ssh_url'],
                    'private': repo_data['private'],
                    'fork': repo_data['fork'],
                    'language': repo_data.get('language', ''),
                    'stargazers_count': repo_data['stargazers_count'],
                    'watchers_count': repo_data['watchers_count'],
                    'forks_count': repo_data['forks_count'],
                    'open_issues_count': repo_data['open_issues_count'],
                    'default_branch': repo_data.get('default_branch', 'main'),
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'pushed_at': pushed_at,
                }
            )
            saved_count += 1

        messages.success(request, f'Successfully fetched {saved_count} repositories from GitHub!')

    except requests.RequestException as e:
        messages.error(request, f'Error fetching repositories: {str(e)}')

    return redirect('github:index')


@login_required
@require_POST
def request_code_change(request):
    """Handle AI-powered code change requests."""
    try:
        # Parse JSON body
        data = json.loads(request.body)
        repo_id = data.get('repo_id')
        change_request = data.get('change_request')

        logger.info(f"Code change request received from user: {request.user.username}")
        logger.info(f"Repository ID: {repo_id}, Request: {change_request[:100]}...")

        if not repo_id or not change_request:
            logger.warning("Missing required fields in code change request")
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        # Get the repository
        try:
            repository = GitHubRepository.objects.get(
                id=repo_id,
                connection__user=request.user
            )
            logger.info(f"Repository found: {repository.full_name}")
        except GitHubRepository.DoesNotExist:
            logger.error(f"Repository not found with ID: {repo_id} for user: {request.user.username}")
            return JsonResponse({
                'success': False,
                'error': 'Repository not found'
            }, status=404)

        # Check if user has GitHub connection
        try:
            github_connection = request.user.github_connection
            logger.info(f"GitHub connection verified for user: {github_connection.github_username}")
        except GitHubConnection.DoesNotExist:
            logger.error(f"No GitHub connection found for user: {request.user.username}")
            return JsonResponse({
                'success': False,
                'error': 'GitHub account not connected'
            }, status=400)

        # Create code change request record
        code_change_request = CodeChangeRequest.objects.create(
            repository=repository,
            user=request.user,
            change_request=change_request,
            status='pending'
        )
        logger.info(f"Created CodeChangeRequest with ID: {code_change_request.id}")

        # Log the initial request
        code_change_request.add_log(f"Request created by user: {request.user.username}")
        code_change_request.add_log(f"Repository: {repository.full_name}")
        code_change_request.add_log(f"Change request: {change_request}")

        # Execute the code change in a background thread
        def execute_code_change():
            try:
                logger.info(f"Starting background thread for request ID: {code_change_request.id}")
                service = CodeChangeService(
                    github_connection=github_connection,
                    repository=repository,
                    change_request_obj=code_change_request
                )
                service.execute()
                logger.info(f"Background thread completed for request ID: {code_change_request.id}")
            except Exception as e:
                logger.error(f"Background thread error for request ID {code_change_request.id}: {str(e)}")

        thread = threading.Thread(target=execute_code_change)
        thread.daemon = True
        thread.start()
        logger.info(f"Background thread started for request ID: {code_change_request.id}")

        return JsonResponse({
            'success': True,
            'message': 'Code change request submitted. Processing in background...',
            'request_id': code_change_request.id
        })

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON received: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in request_code_change: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_code_change_status(request, request_id):
    """Get the current status and logs for a code change request."""
    try:
        code_change_request = CodeChangeRequest.objects.get(
            id=request_id,
            user=request.user
        )

        return JsonResponse({
            'success': True,
            'status': code_change_request.status,
            'branch_name': code_change_request.branch_name,
            'error_message': code_change_request.error_message,
            'execution_log': code_change_request.execution_log or '',
            'codex_logs': code_change_request.codex_logs or '',
            'created_at': code_change_request.created_at.isoformat(),
            'completed_at': code_change_request.completed_at.isoformat() if code_change_request.completed_at else None
        })

    except CodeChangeRequest.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Code change request not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error fetching code change status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
