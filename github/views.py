import requests
import secrets
from datetime import datetime
from urllib.parse import urlencode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from .models import GitHubConnection, GitHubRepository
import threading


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

