from django.urls import path

from .views import JwtLoginView, JwtLogoutView, JwtSignupView

app_name = "rest_accounts"

urlpatterns = [
    path("api/login/", JwtLoginView.as_view(), name="api_login"),
    path("api/logout/", JwtLogoutView.as_view(), name="api_logout"),
    path("api/signup/", JwtSignupView.as_view(), name="api_signup"),
]
