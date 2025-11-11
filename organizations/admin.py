from django.contrib import admin
from .models import (
    Organization, Department, Team, Role,
    OrganizationMember, TeamMember
)


def get_user_organizations(user):
    """Helper function to get organizations for a user"""
    if user.is_superuser:
        return Organization.objects.all()

    # Get organizations where user is a member with ADMIN role
    admin_memberships = OrganizationMember.objects.filter(
        user=user,
        role__role_type='ADMIN'
    ).select_related('organization')

    return Organization.objects.filter(
        id__in=admin_memberships.values_list('organization_id', flat=True)
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'email', 'parent_organization', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'country']
    search_fields = ['name', 'slug', 'email', 'tax_id']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'parent_organization', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'website')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Legal & Tax', {
            'fields': ('tax_id', 'registration_number')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter organizations based on user role"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(id__in=get_user_organizations(request.user).values_list('id', flat=True))

    def has_change_permission(self, request, obj=None):
        """Only allow changes to organizations the user is admin of"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj in get_user_organizations(request.user)

    def has_delete_permission(self, request, obj=None):
        """Only allow deletion of organizations the user is admin of"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return False
        return obj in get_user_organizations(request.user)

    def has_view_permission(self, request, obj=None):
        """Only allow viewing organizations the user is admin of"""
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj in get_user_organizations(request.user)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'head', 'budget_allocated', 'is_active', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['organization', 'parent_department', 'head']

    fieldsets = (
        ('Basic Information', {
            'fields': ('organization', 'name', 'slug', 'description', 'parent_department')
        }),
        ('Management', {
            'fields': ('head', 'budget_allocated', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter departments based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter organization choices in forms"""
        if db_field.name == "organization" and not request.user.is_superuser:
            kwargs["queryset"] = get_user_organizations(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'department', 'lead', 'project_key', 'budget_allocated', 'is_active', 'created_at']
    list_filter = ['is_active', 'department__organization', 'created_at']
    search_fields = ['name', 'slug', 'description', 'project_key']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['department', 'lead']

    fieldsets = (
        ('Basic Information', {
            'fields': ('department', 'name', 'slug', 'description')
        }),
        ('Project & Management', {
            'fields': ('lead', 'project_key', 'budget_allocated', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter teams based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(department__organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter department choices in forms"""
        if db_field.name == "department" and not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            kwargs["queryset"] = Department.objects.filter(organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'role_type', 'created_at']
    list_filter = ['role_type', 'organization', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['organization']

    fieldsets = (
        ('Basic Information', {
            'fields': ('organization', 'name', 'role_type', 'description')
        }),
        ('User Management Permissions', {
            'fields': ('can_manage_users', 'can_manage_roles')
        }),
        ('Financial Permissions', {
            'fields': ('can_view_all_financial', 'can_manage_financial', 'can_approve_expenses')
        }),
        ('Organizational Permissions', {
            'fields': ('can_manage_departments', 'can_manage_teams')
        }),
        ('Reporting Permissions', {
            'fields': ('can_view_reports', 'can_export_data')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter roles based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter organization choices in forms"""
        if db_field.name == "organization" and not request.user.is_superuser:
            kwargs["queryset"] = get_user_organizations(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'department', 'role', 'job_title', 'is_active', 'date_joined']
    list_filter = ['is_active', 'organization', 'role', 'date_joined']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name', 'employee_id', 'job_title']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['user', 'organization', 'department', 'role']
    date_hierarchy = 'date_joined'

    fieldsets = (
        ('Membership', {
            'fields': ('user', 'organization', 'department', 'role', 'is_active')
        }),
        ('Employment Details', {
            'fields': ('employee_id', 'job_title', 'salary')
        }),
        ('Dates', {
            'fields': ('date_joined', 'date_left')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Filter organization members based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "organization":
                kwargs["queryset"] = user_orgs
            elif db_field.name == "department":
                kwargs["queryset"] = Department.objects.filter(organization__in=user_orgs)
            elif db_field.name == "role":
                kwargs["queryset"] = Role.objects.filter(organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['member', 'team', 'is_lead', 'is_active', 'joined_at']
    list_filter = ['is_active', 'is_lead', 'team__department__organization', 'joined_at']
    search_fields = ['member__user__username', 'member__user__email', 'team__name']
    readonly_fields = ['joined_at']
    autocomplete_fields = ['member', 'team']
    date_hierarchy = 'joined_at'

    fieldsets = (
        ('Team Membership', {
            'fields': ('member', 'team', 'is_lead', 'is_active')
        }),
        ('Dates', {
            'fields': ('joined_at', 'left_at')
        }),
    )

    def get_queryset(self, request):
        """Filter team members based on user's organizations"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        user_orgs = get_user_organizations(request.user)
        return qs.filter(team__department__organization__in=user_orgs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key choices in forms"""
        if not request.user.is_superuser:
            user_orgs = get_user_organizations(request.user)
            if db_field.name == "member":
                kwargs["queryset"] = OrganizationMember.objects.filter(organization__in=user_orgs)
            elif db_field.name == "team":
                kwargs["queryset"] = Team.objects.filter(department__organization__in=user_orgs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
