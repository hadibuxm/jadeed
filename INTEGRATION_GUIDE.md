# Integration Guide: Adding Accounting to Sign-up/Sign-in

This guide shows how to integrate the new accounting system with your existing authentication flow.

## Overview

The accounting system needs to create an `OrganizationMember` record when users sign up or sign in. This links the Django `User` to an `Organization` with a specific `Role`.

## Implementation Options

### Option 1: Auto-create Organization on First Sign-up

For new users signing up, automatically create a new organization with them as admin.

```python
# In your sign-up view (e.g., apps/accounts/views.py)
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils.text import slugify
from organizations.models import Organization, Role, OrganizationMember, Department

def signup_view(request):
    if request.method == 'POST':
        # Your existing user creation logic
        user = User.objects.create_user(
            username=request.POST['username'],
            email=request.POST['email'],
            password=request.POST['password'],
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', '')
        )

        # Create organization for the new user
        org_name = f"{user.get_full_name() or user.username}'s Organization"
        org = Organization.objects.create(
            name=org_name,
            slug=slugify(org_name),
            email=user.email,
            is_active=True
        )

        # Create default roles for the organization
        Role.create_default_roles(org)

        # Create default department
        department = Department.objects.create(
            organization=org,
            name='General',
            slug='general',
            description='Default department',
            head=user
        )

        # Make user an admin of their organization
        admin_role = Role.objects.get(organization=org, role_type=Role.ADMIN)
        OrganizationMember.objects.create(
            user=user,
            organization=org,
            department=department,
            role=admin_role,
            job_title='Owner',
            is_active=True
        )

        login(request, user)
        messages.success(request, f'Welcome! Your organization "{org_name}" has been created.')
        return redirect('accounts:index')

    return render(request, 'accounts/signup.html')
```

### Option 2: Join Existing Organization

Allow users to join an existing organization by invitation code or organization slug.

```python
# In your sign-up view
from organizations.models import Organization, Role, OrganizationMember

def signup_with_org_view(request):
    if request.method == 'POST':
        # Create user
        user = User.objects.create_user(...)

        # Check if joining existing organization
        org_slug = request.POST.get('organization_slug')
        if org_slug:
            try:
                org = Organization.objects.get(slug=org_slug, is_active=True)

                # Get or create a default department
                department = org.departments.first()

                # Assign employee role by default
                employee_role = Role.objects.get(
                    organization=org,
                    role_type=Role.EMPLOYEE
                )

                OrganizationMember.objects.create(
                    user=user,
                    organization=org,
                    department=department,
                    role=employee_role,
                    is_active=True
                )

                messages.success(request, f'Welcome! You have joined {org.name}.')
            except Organization.DoesNotExist:
                messages.error(request, 'Organization not found.')
        else:
            # Create new organization (Option 1 logic)
            pass

        login(request, user)
        return redirect('accounts:index')

    return render(request, 'accounts/signup.html')
```

### Option 3: Organization Setup After Sign-up

Let users complete organization setup after initial registration.

```python
# apps/accounts/views.py
from organizations.permissions import require_organization_member

def index_view(request):
    """Main dashboard - check if user has organization membership"""
    if request.user.is_authenticated:
        member = get_user_organization_member(request.user)
        if not member:
            # Redirect to organization setup
            return redirect('organizations:setup')

    return render(request, 'accounts/index.html')

# organizations/views.py (create this file)
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.text import slugify
from .models import Organization, Department, Role, OrganizationMember

@login_required
def organization_setup_view(request):
    """Setup organization for new users"""
    # Check if user already has an organization
    existing_member = get_user_organization_member(request.user)
    if existing_member:
        messages.info(request, 'You are already part of an organization.')
        return redirect('accounts:index')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            # Create new organization
            org_name = request.POST['organization_name']
            org = Organization.objects.create(
                name=org_name,
                slug=slugify(org_name),
                email=request.POST['email'],
                phone=request.POST.get('phone', ''),
                is_active=True
            )

            # Create default roles
            Role.create_default_roles(org)

            # Create default department
            department = Department.objects.create(
                organization=org,
                name='General',
                slug='general',
                head=request.user
            )

            # Make user admin
            admin_role = Role.objects.get(organization=org, role_type=Role.ADMIN)
            OrganizationMember.objects.create(
                user=request.user,
                organization=org,
                department=department,
                role=admin_role,
                job_title=request.POST.get('job_title', 'Owner'),
                is_active=True
            )

            messages.success(request, f'Organization "{org_name}" created successfully!')
            return redirect('accounts:index')

        elif action == 'join':
            # Join existing organization
            org_slug = request.POST['organization_slug']
            try:
                org = Organization.objects.get(slug=org_slug, is_active=True)
                department = org.departments.first()
                employee_role = Role.objects.get(
                    organization=org,
                    role_type=Role.EMPLOYEE
                )

                OrganizationMember.objects.create(
                    user=request.user,
                    organization=org,
                    department=department,
                    role=employee_role,
                    is_active=True
                )

                messages.success(request, f'Successfully joined {org.name}!')
                return redirect('accounts:index')

            except Organization.DoesNotExist:
                messages.error(request, 'Organization not found.')

    return render(request, 'organizations/setup.html')
```

## Sign-in Flow

When users sign in, check if they have an organization membership:

```python
# apps/accounts/views.py
from django.contrib.auth import authenticate, login
from organizations.permissions import get_user_organization_member

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Check if user has organization membership
            member = get_user_organization_member(user)
            if not member:
                messages.warning(
                    request,
                    'Please complete your organization setup.'
                )
                return redirect('organizations:setup')

            messages.success(
                request,
                f'Welcome back! You are signed in as {member.role.get_role_type_display()}'
            )
            return redirect('accounts:index')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')
```

## Template Example

Organization setup template (`organizations/templates/organizations/setup.html`):

```html
{% extends 'base.html' %}

{% block content %}
<div class="container mt-5">
    <h2>Organization Setup</h2>
    <p>Welcome! Please set up your organization or join an existing one.</p>

    <div class="row mt-4">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h4>Create New Organization</h4>
                </div>
                <div class="card-body">
                    <form method="post">
                        {% csrf_token %}
                        <input type="hidden" name="action" value="create">

                        <div class="mb-3">
                            <label for="organization_name" class="form-label">Organization Name</label>
                            <input type="text" class="form-control" id="organization_name"
                                   name="organization_name" required>
                        </div>

                        <div class="mb-3">
                            <label for="email" class="form-label">Organization Email</label>
                            <input type="email" class="form-control" id="email"
                                   name="email" value="{{ user.email }}" required>
                        </div>

                        <div class="mb-3">
                            <label for="phone" class="form-label">Phone (Optional)</label>
                            <input type="tel" class="form-control" id="phone" name="phone">
                        </div>

                        <div class="mb-3">
                            <label for="job_title" class="form-label">Your Job Title</label>
                            <input type="text" class="form-control" id="job_title"
                                   name="job_title" value="Owner">
                        </div>

                        <button type="submit" class="btn btn-primary">Create Organization</button>
                    </form>
                </div>
            </div>
        </div>

        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h4>Join Existing Organization</h4>
                </div>
                <div class="card-body">
                    <form method="post">
                        {% csrf_token %}
                        <input type="hidden" name="action" value="join">

                        <div class="mb-3">
                            <label for="organization_slug" class="form-label">Organization Code</label>
                            <input type="text" class="form-control" id="organization_slug"
                                   name="organization_slug" required>
                            <div class="form-text">Ask your administrator for the organization code.</div>
                        </div>

                        <button type="submit" class="btn btn-secondary">Join Organization</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## URL Configuration

Add to your `organizations/urls.py`:

```python
from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('setup/', views.organization_setup_view, name='setup'),
    # Add more URLs as needed
]
```

And include in main `urls.py`:

```python
urlpatterns = [
    # ... existing patterns
    path('organizations/', include('organizations.urls')),
]
```

## Displaying Organization Info

In your base template or dashboard, show organization context:

```html
<!-- templates/base.html or templates/accounts/index.html -->
{% if user_organization_member %}
<div class="user-org-info">
    <span class="organization">{{ user_organization.name }}</span>
    <span class="role badge bg-primary">{{ user_role.get_role_type_display }}</span>
    <span class="department">{{ user_department.name }}</span>
</div>

<!-- Show role-based menu items -->
<nav>
    <a href="{% url 'accounts:index' %}">Dashboard</a>

    {% if user_role.can_approve_expenses %}
    <a href="{% url 'accounting:expenses' %}">Expenses</a>
    {% endif %}

    {% if user_role.can_manage_financial %}
    <a href="{% url 'accounting:invoices' %}">Invoices</a>
    <a href="{% url 'accounting:accounts' %}">Chart of Accounts</a>
    {% endif %}

    {% if user_role.can_manage_users %}
    <a href="{% url 'organizations:members' %}">Manage Team</a>
    {% endif %}

    {% if user_role.can_view_reports %}
    <a href="{% url 'accounting:reports' %}">Reports</a>
    {% endif %}
</nav>
{% else %}
<div class="alert alert-warning">
    Please <a href="{% url 'organizations:setup' %}">set up your organization</a> to get started.
</div>
{% endif %}
```

## Recommended Flow

For your Jadeed application, I recommend:

1. **On Sign-up**: Auto-create organization (Option 1)
   - Simple for new users
   - Each user starts as admin of their own organization
   - Can invite others later

2. **On Sign-in**: Check organization membership
   - If missing, redirect to setup
   - Show organization info in navbar

3. **Dashboard**: Show role-appropriate features
   - Use template conditionals based on permissions
   - Hide features user doesn't have access to

4. **Later**: Add invitation system
   - Admins can invite users to their organization
   - Generate invitation links/codes
   - Set role during invitation

This provides a smooth onboarding experience while maintaining the organizational structure and permissions!
