from django.contrib import admin
from .models import (
    Project, WorkflowStep, Vision, Initiative,
    Portfolio, Product, Feature, ProductStep, FeatureStep, RecentItem,
    WorkflowComment, WorkflowActionLog, WorkflowDocument,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'github_repository', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'title', 'step_type', 'project', 'parent_step', 'is_completed', 'created_at')
    list_filter = ('step_type', 'is_completed', 'created_at')
    search_fields = ('title', 'description', 'reference_id')
    readonly_fields = ('reference_id', 'created_at', 'updated_at', 'readme_generated_at')


@admin.register(Vision)
class VisionAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'strategic_goals')


@admin.register(Initiative)
class InitiativeAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'timeline')


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'scope')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'value_proposition')


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'priority', 'repository')
    list_filter = ('priority', 'repository')


@admin.register(ProductStep)
class ProductStepAdmin(admin.ModelAdmin):
    list_display = ('title', 'step_type', 'layer', 'product', 'order', 'is_completed', 'created_at')
    list_filter = ('step_type', 'layer', 'is_completed', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'document_generated_at')
    ordering = ('product', 'order', 'created_at')


@admin.register(FeatureStep)
class FeatureStepAdmin(admin.ModelAdmin):
    list_display = ('title', 'step_type', 'layer', 'feature', 'order', 'is_completed', 'created_at')
    list_filter = ('step_type', 'layer', 'is_completed', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'document_generated_at')
    ordering = ('feature', 'order', 'created_at')


@admin.register(RecentItem)
class RecentItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_type', 'item_title', 'accessed_at')
    list_filter = ('item_type', 'accessed_at', 'user')
    search_fields = ('item_title', 'user__username')
    readonly_fields = ('accessed_at',)
    ordering = ('-accessed_at',)


@admin.register(WorkflowComment)
class WorkflowCommentAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content', 'workflow_step__title', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WorkflowActionLog)
class WorkflowActionLogAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'action_type', 'user', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('workflow_step__title', 'description', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(WorkflowDocument)
class WorkflowDocumentAdmin(admin.ModelAdmin):
    list_display = ('workflow_step', 'document_type', 'title', 'created_by', 'created_at')
    list_filter = ('document_type', 'created_at')
    search_fields = ('title', 'workflow_step__title', 'created_by__username')
    readonly_fields = ('created_at',)
