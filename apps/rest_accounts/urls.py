from django.urls import path

from .views import JwtLoginView, JwtLogoutView, JwtSignupView, UserProfileView
from rest_framework_simplejwt.views import TokenRefreshView

app_name = "rest_accounts"

urlpatterns = [
    path("api/login/", JwtLoginView.as_view(), name="api_login"),
    path("api/logout/", JwtLogoutView.as_view(), name="api_logout"),
    path("api/signup/", JwtSignupView.as_view(), name="api_signup"),
    path("api/me/", UserProfileView.as_view(), name="api_user_profile"),
    path("api/refresh/", TokenRefreshView.as_view(), name="api_refresh"),
]
