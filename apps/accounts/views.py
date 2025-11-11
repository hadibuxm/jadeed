from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import login
from django.contrib import messages
from django.utils.text import slugify
from django.db import transaction
from decimal import Decimal

from .forms import SignUpForm, BootstrapAuthenticationForm
from organizations.models import Organization, Department, Role, OrganizationMember
from organizations.permissions import get_user_organization_member


def index(request):
    """Main dashboard - check if user has organization membership"""
    if request.user.is_authenticated:
        member = get_user_organization_member(request.user)
        if not member:
            messages.warning(
                request,
                'Please complete your organization setup to continue.'
            )
            # You can add an organization setup view later if needed
    return render(request, "accounts/index.html")


class AccountsLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = BootstrapAuthenticationForm

    def get_success_url(self):
        """Check organization membership after login"""
        member = get_user_organization_member(self.request.user)
        if member:
            messages.success(
                self.request,
                f'Welcome back! You are signed in as {member.role.get_role_type_display()}.'
            )
        else:
            messages.warning(
                self.request,
                'Your account needs to be added to an organization. Please contact an administrator.'
            )
        return reverse_lazy("accounts:index")


class AccountsLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:index")

    @transaction.atomic
    def form_valid(self, form):
        """Create user and automatically set up their organization"""
        # Save the user
        user = form.save(commit=False)
        user.email = form.cleaned_data['email']
        user.first_name = form.cleaned_data.get('first_name', '')
        user.last_name = form.cleaned_data.get('last_name', '')

        # Make user staff and superuser so they can access admin panel
        user.is_staff = True
        user.is_superuser = True

        user.save()

        # Get organization data from form
        org_name = form.cleaned_data['organization_name']
        job_title = form.cleaned_data.get('job_title', 'Owner')
        phone = form.cleaned_data.get('phone', '')

        # Create the organization
        org = Organization.objects.create(
            name=org_name,
            slug=slugify(org_name),
            email=user.email,
            phone=phone,
            is_active=True
        )

        # Create default roles for the organization
        Role.create_default_roles(org)

        # Create a default "General" department
        department = Department.objects.create(
            organization=org,
            name='General',
            slug='general',
            description='Default department for the organization',
            head=user,
            budget_allocated=Decimal('0.00')
        )

        # Get the ADMIN role and make the user an admin of their organization
        admin_role = Role.objects.get(organization=org, role_type=Role.ADMIN)
        OrganizationMember.objects.create(
            user=user,
            organization=org,
            department=department,
            role=admin_role,
            employee_id='EMP001',
            job_title=job_title,
            is_active=True
        )

        # Log the user in
        login(self.request, user)

        # Success message
        messages.success(
            self.request,
            f'Welcome! Your organization "{org_name}" has been created successfully. '
            f'You are now signed in as an Administrator.'
        )

        return redirect(self.success_url)

# Create your views here.
