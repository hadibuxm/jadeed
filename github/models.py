from django.db import models
from django.contrib.auth.models import User


class GitHubConnection(models.Model):
    """Stores GitHub OAuth connection for a user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='github_connection')
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)
    token_type = models.CharField(max_length=50, default='bearer')
    scope = models.TextField(blank=True)
    github_user_id = models.CharField(max_length=100, blank=True)
    github_username = models.CharField(max_length=255, blank=True)
    github_avatar_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - GitHub Connection"

    class Meta:
        verbose_name = "GitHub Connection"
        verbose_name_plural = "GitHub Connections"


class GitHubRepository(models.Model):
    """Stores cached GitHub repository data."""
    connection = models.ForeignKey(GitHubConnection, on_delete=models.CASCADE, related_name='repositories')
    repo_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=500)
    description = models.TextField(blank=True, null=True)
    html_url = models.URLField()
    clone_url = models.URLField()
    ssh_url = models.CharField(max_length=500)
    private = models.BooleanField(default=False)
    fork = models.BooleanField(default=False)
    language = models.CharField(max_length=100, blank=True, null=True)
    stargazers_count = models.IntegerField(default=0)
    watchers_count = models.IntegerField(default=0)
    forks_count = models.IntegerField(default=0)
    open_issues_count = models.IntegerField(default=0)
    default_branch = models.CharField(max_length=100, default='main')
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    pushed_at = models.DateTimeField(null=True, blank=True)
    last_synced = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "GitHub Repository"
        verbose_name_plural = "GitHub Repositories"
        unique_together = ['connection', 'repo_id']
        ordering = ['-updated_at']


        ordering = ['-created_at']
