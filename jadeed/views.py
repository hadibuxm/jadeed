from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode


def home_redirect(request):
    """Redirect home visitors based on authentication state."""
    if request.user.is_authenticated:
        return redirect("jira:issues")
    login_url = reverse("accounts:login")
    params = urlencode({"next": request.get_full_path()})
    return redirect(f"{login_url}?{params}")
