"""
Permission decorators and utilities for role-based access control
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import OrganizationMember


def get_user_organization_member(user, organization=None):
    """
    Get the OrganizationMember instance for a user.
    If organization is provided, get membership for that specific organization.
    Otherwise, get the user's primary/first organization membership.
    """
    if not user.is_authenticated:
        return None

    try:
        if organization:
            return OrganizationMember.objects.select_related('role', 'organization', 'department').get(
                user=user,
                organization=organization,
                is_active=True
            )
        else:
            # Get first active membership
            return OrganizationMember.objects.select_related('role', 'organization', 'department').filter(
                user=user,
                is_active=True
            ).first()
    except OrganizationMember.DoesNotExist:
        return None


def user_has_permission(user, permission_name, organization=None):
    """
    Check if a user has a specific permission.

    Args:
        user: Django User instance
        permission_name: Permission attribute name (e.g., 'can_manage_users')
        organization: Optional Organization instance to check permission for

    Returns:
        Boolean indicating if user has the permission
    """
    if not user.is_authenticated:
        return False

    # Superusers have all permissions
    if user.is_superuser:
        return True

    member = get_user_organization_member(user, organization)
    if not member:
        return False

    return member.has_permission(permission_name)


def require_permission(permission_name, redirect_url=None, raise_exception=False):
    """
    Decorator to check if user has a specific permission.

    Usage:
        @require_permission('can_manage_users')
        def my_view(request):
            ...

    Args:
        permission_name: Permission attribute name to check
        redirect_url: URL to redirect to if permission denied (default: '/')
        raise_exception: If True, raise PermissionDenied instead of redirecting
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get organization from kwargs if available
            organization_id = kwargs.get('organization_id')
            organization = None

            if organization_id:
                from .models import Organization
                try:
                    organization = Organization.objects.get(id=organization_id)
                except Organization.DoesNotExist:
                    if raise_exception:
                        raise PermissionDenied("Organization not found")
                    messages.error(request, "Organization not found")
                    return redirect(redirect_url or '/')

            # Check permission
            if not user_has_permission(request.user, permission_name, organization):
                if raise_exception:
                    raise PermissionDenied(f"You don't have permission: {permission_name}")

                messages.error(request, f"You don't have permission to access this page")
                return redirect(redirect_url or '/')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(role_type, redirect_url=None, raise_exception=False):
    """
    Decorator to check if user has a specific role type.

    Usage:
        @require_role('ADMIN')
        def my_view(request):
            ...

    Args:
        role_type: Role type constant (e.g., 'ADMIN', 'MANAGER')
        redirect_url: URL to redirect to if access denied
        raise_exception: If True, raise PermissionDenied instead of redirecting
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if raise_exception:
                    raise PermissionDenied("Authentication required")
                return redirect('login')

            # Superusers bypass role checks
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Get organization from kwargs if available
            organization_id = kwargs.get('organization_id')
            organization = None

            if organization_id:
                from .models import Organization
                try:
                    organization = Organization.objects.get(id=organization_id)
                except Organization.DoesNotExist:
                    if raise_exception:
                        raise PermissionDenied("Organization not found")
                    messages.error(request, "Organization not found")
                    return redirect(redirect_url or '/')

            member = get_user_organization_member(request.user, organization)
            if not member or member.role.role_type != role_type:
                if raise_exception:
                    raise PermissionDenied(f"You must have {role_type} role to access this page")

                messages.error(request, f"You must have {role_type} role to access this page")
                return redirect(redirect_url or '/')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_organization_member(redirect_url=None, raise_exception=False):
    """
    Decorator to check if user is a member of any organization.

    Usage:
        @require_organization_member
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if raise_exception:
                    raise PermissionDenied("Authentication required")
                return redirect('login')

            # Superusers bypass this check
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            member = get_user_organization_member(request.user)
            if not member:
                if raise_exception:
                    raise PermissionDenied("You must be a member of an organization")

                messages.error(request, "You must be a member of an organization to access this page")
                return redirect(redirect_url or '/')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class PermissionMixin:
    """
    Mixin for views that need permission checking.
    Can be used with class-based views.

    Usage:
        class MyView(PermissionMixin, View):
            required_permission = 'can_manage_users'

            def get(self, request):
                ...
    """
    required_permission = None
    required_role = None
    permission_denied_url = '/'
    raise_permission_exception = False

    def dispatch(self, request, *args, **kwargs):
        # Check authentication
        if not request.user.is_authenticated:
            return redirect('login')

        # Superusers bypass all checks
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        # Get organization context
        organization_id = kwargs.get('organization_id')
        organization = None

        if organization_id:
            from .models import Organization
            try:
                organization = Organization.objects.get(id=organization_id)
            except Organization.DoesNotExist:
                if self.raise_permission_exception:
                    raise PermissionDenied("Organization not found")
                messages.error(request, "Organization not found")
                return redirect(self.permission_denied_url)

        # Check if user is organization member
        member = get_user_organization_member(request.user, organization)
        if not member:
            if self.raise_permission_exception:
                raise PermissionDenied("You must be a member of an organization")
            messages.error(request, "You must be a member of an organization")
            return redirect(self.permission_denied_url)

        # Check required role
        if self.required_role and member.role.role_type != self.required_role:
            if self.raise_permission_exception:
                raise PermissionDenied(f"You must have {self.required_role} role")
            messages.error(request, f"You must have {self.required_role} role")
            return redirect(self.permission_denied_url)

        # Check required permission
        if self.required_permission and not member.has_permission(self.required_permission):
            if self.raise_permission_exception:
                raise PermissionDenied(f"You don't have permission: {self.required_permission}")
            messages.error(request, "You don't have permission to access this page")
            return redirect(self.permission_denied_url)

        return super().dispatch(request, *args, **kwargs)
