"""
GitHub API views for Next.js frontend integration.
Returns JSON responses for all endpoints.
"""
import requests
import secrets
import logging
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlencode
from django.shortcuts import redirect
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import GitHubConnection, GitHubRepository

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def github_status(request):
    """Get GitHub connection status and repositories."""
    try:
        github_connection = request.user.github_connection
        
        # Serialize connection data
        connection_data = {
            'github_username': github_connection.github_username,
            'avatar_url': github_connection.github_avatar_url,
            'connected_at': github_connection.created_at.isoformat(),
        }
        
        # Get repositories
        repositories = github_connection.repositories.all()
        repos_data = [
            {
                'id': repo.id,
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description or '',
                'private': repo.private,
                'html_url': repo.html_url,
                'default_branch': repo.default_branch,
                'language': repo.language or '',
                'stars_count': repo.stargazers_count,
                'forks_count': repo.forks_count,
                'updated_at': repo.updated_at.isoformat() if repo.updated_at else None,
                'fork': repo.fork,
            }
            for repo in repositories
        ]
        
        return JsonResponse({
            'has_connection': True,
            'connection': connection_data,
            'repositories': repos_data,
        })
        
    except GitHubConnection.DoesNotExist:
        return JsonResponse({
            'has_connection': False,
            'connection': None,
            'repositories': [],
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def github_connect(request):
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
    
    # Redirect to GitHub OAuth
    return HttpResponseRedirect(auth_url)


@api_view(['GET'])
def github_callback(request):
    """
    Handle GitHub OAuth callback.
    Note: This endpoint doesn't require authentication as it's called by GitHub.
    """
    # Verify state parameter
    state = request.GET.get('state')
    saved_state = request.session.get('github_oauth_state')
    
    if not state or state != saved_state:
        logger.error('Invalid state parameter in GitHub callback')
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=invalid_state')
    
    # Get authorization code
    code = request.GET.get('code')
    if not code:
        logger.error('No authorization code received from GitHub')
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=no_code')
    
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
            logger.error('Failed to obtain access token from GitHub')
            return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=no_token')
        
        # Get user information from GitHub
        user_url = 'https://api.github.com/user'
        user_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        }
        user_response = requests.get(user_url, headers=user_headers)
        user_response.raise_for_status()
        user_data = user_response.json()
        
        # Get user from session (they should be logged in)
        if not request.user.is_authenticated:
            logger.error('User not authenticated during GitHub callback')
            return HttpResponseRedirect(f'{settings.FRONTEND_URL}/login?error=not_authenticated')
        
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
        
        logger.info(f'GitHub connection {"created" if created else "updated"} for user {request.user.username}')
        
        # Automatically sync repositories
        sync_repositories_internal(github_connection)
        
        # Clean up session
        if 'github_oauth_state' in request.session:
            del request.session['github_oauth_state']
        
        # Redirect to frontend with success
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?connected=true')
        
    except requests.RequestException as e:
        logger.error(f'Error during GitHub OAuth: {str(e)}')
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=oauth_failed')
    except Exception as e:
        logger.error(f'Unexpected error in GitHub callback: {str(e)}', exc_info=True)
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=server_error')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def github_sync(request):
    """Sync repositories from GitHub."""
    try:
        github_connection = request.user.github_connection
    except GitHubConnection.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'GitHub account not connected'
        }, status=400)
    
    try:
        synced_count = sync_repositories_internal(github_connection)
        
        # Get updated repositories
        repositories = github_connection.repositories.all()
        repos_data = [
            {
                'id': repo.id,
                'name': repo.name,
                'full_name': repo.full_name,
                'description': repo.description or '',
                'private': repo.private,
                'html_url': repo.html_url,
                'default_branch': repo.default_branch,
                'language': repo.language or '',
                'stars_count': repo.stargazers_count,
                'forks_count': repo.forks_count,
                'updated_at': repo.updated_at.isoformat() if repo.updated_at else None,
                'fork': repo.fork,
            }
            for repo in repositories
        ]
        
        return JsonResponse({
            'success': True,
            'synced_count': synced_count,
            'repositories': repos_data,
        })
        
    except Exception as e:
        logger.error(f'Error syncing repositories: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def github_disconnect(request):
    """Disconnect GitHub account."""
    try:
        github_connection = request.user.github_connection
        github_connection.delete()
        
        logger.info(f'GitHub disconnected for user {request.user.username}')
        
        return JsonResponse({
            'success': True,
            'message': 'GitHub account disconnected successfully'
        })
        
    except GitHubConnection.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No GitHub connection found'
        }, status=404)


def sync_repositories_internal(github_connection):
    """
    Internal function to sync repositories from GitHub.
    Returns the number of repositories synced.
    """
    repos_url = 'https://api.github.com/user/repos'
    headers = {
        'Authorization': f'Bearer {github_connection.access_token}',
        'Accept': 'application/json',
    }
    params = {
        'per_page': 100,
        'sort': 'updated',
    }
    
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
        
        if page > 100:  # Safety limit
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
        created_at = timezone.make_aware(created_at, dt_timezone.utc)
        updated_at = timezone.make_aware(updated_at, dt_timezone.utc)
        if pushed_at:
            pushed_at = timezone.make_aware(pushed_at, dt_timezone.utc)
        
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
    
    logger.info(f'Synced {saved_count} repositories for user {github_connection.user.username}')
    return saved_count
