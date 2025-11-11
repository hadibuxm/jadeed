from django.contrib import admin
from .models import (
    Project, WorkflowStep, Vision, Initiative,
    Portfolio, Product, Feature
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'github_repository', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ('title', 'step_type', 'project', 'parent_step', 'is_completed', 'created_at')
    list_filter = ('step_type', 'is_completed', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'readme_generated_at')


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
    list_display = ('workflow_step', 'priority')
    list_filter = ('priority',)
