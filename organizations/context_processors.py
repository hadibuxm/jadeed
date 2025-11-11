"""
Context processors to add organization and permission data to all templates
"""
from .permissions import get_user_organization_member


def organization_context(request):
    """
    Add current user's organization membership and permissions to template context.

    Available in templates:
    - user_organization_member: OrganizationMember instance
    - user_organization: Organization instance
    - user_role: Role instance
    - user_department: Department instance
    """
    context = {
        'user_organization_member': None,
        'user_organization': None,
        'user_role': None,
        'user_department': None,
    }

    if request.user.is_authenticated:
        member = get_user_organization_member(request.user)
        if member:
            context['user_organization_member'] = member
            context['user_organization'] = member.organization
            context['user_role'] = member.role
            context['user_department'] = member.department

    return context
