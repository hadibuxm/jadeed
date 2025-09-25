from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.views import LoginView, LogoutView
from .forms import SignUpForm, BootstrapAuthenticationForm


def index(request):
    return render(request, "accounts/index.html")


class AccountsLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = BootstrapAuthenticationForm


class AccountsLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")

# Create your views here.
