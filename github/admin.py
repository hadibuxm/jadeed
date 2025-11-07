from django.contrib import admin
from .models import GitHubConnection, GitHubRepository


@admin.register(GitHubConnection)
class GitHubConnectionAdmin(admin.ModelAdmin):
    list_display = ['user', 'github_username', 'github_user_id', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'github_username', 'github_user_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GitHubRepository)
class GitHubRepositoryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'language', 'private', 'stargazers_count', 'forks_count', 'updated_at']
    list_filter = ['private', 'fork', 'language', 'updated_at']
    search_fields = ['name', 'full_name', 'description']
    readonly_fields = ['repo_id', 'created_at', 'updated_at', 'pushed_at', 'last_synced']


