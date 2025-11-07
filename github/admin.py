from django.contrib import admin
from .models import GitHubConnection, GitHubRepository, CodeChangeRequest


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


@admin.register(CodeChangeRequest)
class CodeChangeRequestAdmin(admin.ModelAdmin):
    list_display = ['repository', 'user', 'status', 'branch_name', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at', 'completed_at']
    search_fields = ['repository__full_name', 'user__username', 'change_request', 'branch_name']
    readonly_fields = ['created_at', 'completed_at', 'formatted_execution_log']
    fieldsets = (
        ('Request Information', {
            'fields': ('repository', 'user', 'change_request', 'status')
        }),
        ('Results', {
            'fields': ('branch_name', 'error_message')
        }),
        ('Execution Log', {
            'fields': ('formatted_execution_log',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
    )

    def formatted_execution_log(self, obj):
        """Display execution log with proper formatting."""
        if obj.execution_log:
            from django.utils.html import format_html
            # Convert log to HTML with line breaks
            log_html = obj.execution_log.replace('\n', '<br>')
            return format_html('<div style="font-family: monospace; background-color: #f5f5f5; padding: 10px; white-space: pre-wrap;">{}</div>', log_html)
        return "No logs available"

    formatted_execution_log.short_description = "Execution Log"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('repository', 'user')


