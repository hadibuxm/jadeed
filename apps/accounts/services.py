from decimal import Decimal
from typing import Tuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from organizations.models import Department, Organization, OrganizationMember, Role


User = get_user_model()


@transaction.atomic
def create_user_with_organization(form) -> Tuple[User, Organization, OrganizationMember]:
    """
    Persist a user alongside a default organization scaffold.

    Args:
        form (django.forms.Form): A validated SignUpForm instance.

    Returns:
        tuple: (user, organization, organization_member)
    """
    user = form.save(commit=False)
    user.email = form.cleaned_data["email"]
    user.first_name = form.cleaned_data.get("first_name", "")
    user.last_name = form.cleaned_data.get("last_name", "")

    # Grant initial elevated access so the owner can manage the workspace.
    user.is_staff = True
    user.is_superuser = True
    user.save()

    org_name = form.cleaned_data["organization_name"]
    job_title = form.cleaned_data.get("job_title", "Owner")
    phone = form.cleaned_data.get("phone", "")

    organization = Organization.objects.create(
        name=org_name,
        slug=slugify(org_name),
        email=user.email,
        phone=phone,
        is_active=True,
    )

    Role.create_default_roles(organization)

    department = Department.objects.create(
        organization=organization,
        name="General",
        slug="general",
        description="Default department for the organization",
        head=user,
        budget_allocated=Decimal("0.00"),
    )

    admin_role = Role.objects.get(organization=organization, role_type=Role.ADMIN)
    organization_member = OrganizationMember.objects.create(
        user=user,
        organization=organization,
        department=department,
        role=admin_role,
        employee_id="EMP001",
        job_title=job_title,
        is_active=True,
    )

    return user, organization, organization_member

