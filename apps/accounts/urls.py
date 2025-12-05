from django.urls import path
from . import views, api_views

app_name = "accounts"

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.AccountsLoginView.as_view(), name="login"),
    path("logout/", views.AccountsLogoutView.as_view(), name="logout"),
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("api/login/", api_views.ApiLoginView.as_view(), name="api_login"),
    path("api/logout/", api_views.ApiLogoutView.as_view(), name="api_logout"),
    path("api/signup/", api_views.ApiSignupView.as_view(), name="api_signup"),
]
