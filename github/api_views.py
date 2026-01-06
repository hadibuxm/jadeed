"""
GitHub API views for Next.js frontend integration.
Returns JSON responses for all endpoints.
"""
import json
import base64
import secrets
import logging
from datetime import datetime, timezone as dt_timezone
from urllib.parse import urlencode
from typing import Dict, Any, Optional

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .models import GitHubConnection, GitHubRepository

logger = logging.getLogger(__name__)
User = get_user_model()

# Constants
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_OAUTH_BASE_URL = "https://github.com/login/oauth"
REPOS_PER_PAGE = 100
MAX_PAGES = 100  # Safety limit
DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def serialize_repository(repo: GitHubRepository) -> Dict[str, Any]:
    """Serialize a GitHubRepository instance to dictionary."""
    return {
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


def create_oauth_state(user_id: int) -> str:
    """Create secure OAuth state parameter with embedded user ID."""
    state_data = {
        'random': secrets.token_urlsafe(32),
        'user_id': user_id,
    }
    return base64.urlsafe_b64encode(
        json.dumps(state_data).encode('utf-8')
    ).decode('utf-8')


def decode_oauth_state(state: str) -> Optional[int]:
    """Decode OAuth state parameter to extract user ID."""
    try:
        state_data = json.loads(
            base64.urlsafe_b64decode(state.encode('utf-8')).decode('utf-8')
        )
        return state_data.get('user_id')
    except Exception as e:
        logger.error(f'Failed to decode state parameter: {str(e)}')
        return None


def make_github_request(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> requests.Response:
    """Make a request to GitHub API with error handling."""
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response


def parse_github_date(date_string: Optional[str]) -> Optional[datetime]:
    """Parse GitHub date string to timezone-aware datetime."""
    if not date_string:
        return None
    
    parsed_date = datetime.strptime(date_string, DATE_FORMAT)
    return timezone.make_aware(parsed_date, dt_timezone.utc)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def github_status(request):
    """Get GitHub connection status and repositories."""
    try:
        github_connection = request.user.github_connection
        
        connection_data = {
            'github_username': github_connection.github_username,
            'avatar_url': github_connection.github_avatar_url,
            'connected_at': github_connection.created_at.isoformat(),
        }
        
        repositories = github_connection.repositories.all()
        repos_data = [serialize_repository(repo) for repo in repositories]
        
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
    # Generate secure state parameter
    state = create_oauth_state(request.user.id)
    
    # Store in session as backup
    request.session['github_oauth_state'] = state
    request.session['github_oauth_user_id'] = request.user.id
    
    # Build authorization URL
    params = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'redirect_uri': settings.GITHUB_REDIRECT_URI,
        'scope': settings.GITHUB_SCOPES,
        'state': state,
    }
    auth_url = f"{GITHUB_OAUTH_BASE_URL}/authorize?{urlencode(params)}"
    
    return HttpResponseRedirect(auth_url)


@api_view(['GET'])
def github_callback(request):
    """Handle GitHub OAuth callback."""
    state = request.GET.get('state')
    code = request.GET.get('code')
    
    if not state:
        logger.error('No state parameter in GitHub callback')
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=no_state')
    
    if not code:
        logger.error('No authorization code received from GitHub')
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=no_code')
    
    # Try to decode state parameter to get user ID
    user_id = decode_oauth_state(state)
    
    # Fallback to session-based approach
    if not user_id:
        saved_state = request.session.get('github_oauth_state')
        if not saved_state or saved_state != state:
            logger.error('Invalid state parameter in GitHub callback')
            return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=invalid_state')
        
        user_id = request.session.get('github_oauth_user_id')
    
    if not user_id:
        logger.error('No user ID found in state or session during GitHub callback')
        return HttpResponseRedirect(
            f'{settings.FRONTEND_URL}/login?error=session_expired&message=Please log in again and try connecting GitHub'
        )
    
    try:
        # Get user
        user = User.objects.get(id=user_id)
        
        # Exchange code for access token
        access_token = exchange_code_for_token(code)
        
        # Get user information from GitHub
        user_data = get_github_user_info(access_token)
        
        # Save or update GitHub connection
        github_connection, created = GitHubConnection.objects.update_or_create(
            user=user,
            defaults={
                'access_token': access_token,
                'token_type': 'bearer',
                'scope': settings.GITHUB_SCOPES,
                'github_user_id': str(user_data.get('id', '')),
                'github_username': user_data.get('login', ''),
                'github_avatar_url': user_data.get('avatar_url', ''),
            }
        )
        
        logger.info(f'GitHub connection {"created" if created else "updated"} for user {user.username}')
        
        # Sync repositories synchronously to avoid race condition
        try:
            synced_count = sync_repositories_internal(github_connection)
            logger.info(f'Synced {synced_count} repositories for user {user.username}')
        except Exception as e:
            logger.error(f'Error syncing repositories during OAuth: {str(e)}', exc_info=True)
            # Continue with redirect even if sync fails - user can manually sync later
        
        # Clean up session
        cleanup_oauth_session(request)
        
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?connected=true')
        
    except User.DoesNotExist:
        logger.error(f'User with ID {user_id} not found during GitHub callback')
        return HttpResponseRedirect(
            f'{settings.FRONTEND_URL}/login?error=user_not_found&message=Please log in again and try connecting GitHub'
        )
    except Exception as e:
        logger.error(f'Error in GitHub callback: {str(e)}', exc_info=True)
        return HttpResponseRedirect(f'{settings.FRONTEND_URL}/github?error=server_error')


def exchange_code_for_token(code: str) -> str:
    """Exchange authorization code for access token."""
    token_url = f'{GITHUB_OAUTH_BASE_URL}/access_token'
    token_data = {
        'client_id': settings.GITHUB_CLIENT_ID,
        'client_secret': settings.GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': settings.GITHUB_REDIRECT_URI,
    }
    headers = {'Accept': 'application/json'}
    
    response = requests.post(token_url, data=token_data, headers=headers)
    response.raise_for_status()
    token_response = response.json()
    
    access_token = token_response.get('access_token')
    if not access_token:
        raise ValueError('Failed to obtain access token from GitHub')
    
    return access_token


def get_github_user_info(access_token: str) -> Dict[str, Any]:
    """Get user information from GitHub API."""
    user_url = f'{GITHUB_API_BASE_URL}/user'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    
    response = make_github_request(user_url, headers)
    return response.json()



def cleanup_oauth_session(request) -> None:
    """Clean up OAuth-related session data."""
    session_keys = ['github_oauth_state', 'github_oauth_user_id']
    for key in session_keys:
        if key in request.session:
            del request.session[key]


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
        
        repositories = github_connection.repositories.all()
        repos_data = [serialize_repository(repo) for repo in repositories]
        
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


def sync_repositories_internal(github_connection: GitHubConnection) -> int:
    """Internal function to sync repositories from GitHub."""
    logger.info(f'Starting repository sync for user {github_connection.user.username}')
    
    repos_url = f'{GITHUB_API_BASE_URL}/user/repos'
    headers = {
        'Authorization': f'Bearer {github_connection.access_token}',
        'Accept': 'application/json',
    }
    params = {
        'per_page': REPOS_PER_PAGE,
        'sort': 'updated',
    }
    
    all_repos = []
    page = 1
    
    while page <= MAX_PAGES:
        params['page'] = page
        
        try:
            logger.info(f'Fetching repositories page {page} for user {github_connection.user.username}')
            response = make_github_request(repos_url, headers, params)
            repos = response.json()
            
            if not repos:
                break
            
            all_repos.extend(repos)
            logger.info(f'Fetched {len(repos)} repositories from page {page}')
            page += 1
            
        except requests.RequestException as e:
            logger.error(f'Error fetching repositories page {page}: {str(e)}')
            break
    
    logger.info(f'Total repositories fetched: {len(all_repos)} for user {github_connection.user.username}')
    
    # Save repositories to database
    saved_count = 0
    for repo_data in all_repos:
        try:
            created_at = parse_github_date(repo_data['created_at'])
            updated_at = parse_github_date(repo_data['updated_at'])
            pushed_at = parse_github_date(repo_data.get('pushed_at'))
            
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
            
        except Exception as e:
            logger.error(f'Error saving repository {repo_data.get("name", "unknown")}: {str(e)}')
            continue
    
    logger.info(f'Repository sync completed: {saved_count} repositories saved for user {github_connection.user.username}')
    return saved_count
