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


class CodeChangeRequest(models.Model):
    """Stores AI-powered code change requests for repositories."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('cloning', 'Cloning Repository'),
        ('processing', 'Processing Changes'),
        ('pushing', 'Pushing to GitHub'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    repository = models.ForeignKey(GitHubRepository, on_delete=models.CASCADE, related_name='code_changes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='code_changes')
    change_request = models.TextField(help_text="Description of the code changes requested")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    branch_name = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    execution_log = models.TextField(blank=True, null=True, help_text="Detailed execution log")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.repository.full_name} - {self.status}"

    def add_log(self, message):
        """Add a timestamped log entry."""
        from django.utils import timezone
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        if self.execution_log:
            self.execution_log += log_entry
        else:
            self.execution_log = log_entry
        self.save()

    class Meta:
        verbose_name = "Code Change Request"
        verbose_name_plural = "Code Change Requests"
        ordering = ['-created_at']
