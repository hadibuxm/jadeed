from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import login
from django.contrib import messages
from .forms import SignUpForm, BootstrapAuthenticationForm
from organizations.permissions import get_user_organization_member
from .services import create_user_with_organization


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

    def form_valid(self, form):
        """Create user and automatically set up their organization"""
        user, organization, _ = create_user_with_organization(form)

        # Log the user in
        login(self.request, user)

        # Success message
        messages.success(
            self.request,
            f'Welcome! Your organization "{organization.name}" has been created successfully. '
            f'You are now signed in as an Administrator.'
        )

        return redirect(self.success_url)

# Create your views here.
