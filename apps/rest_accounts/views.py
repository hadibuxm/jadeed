from django.contrib.auth import login
from django.db import IntegrityError
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.services import create_user_with_organization
from organizations.permissions import get_user_organization_member

from .serializers import JwtLoginSerializer, SignupSerializer, serialize_user


class JwtLoginView(TokenObtainPairView):
    """
    Issue JWT access/refresh tokens for username/password credentials.
    """

    serializer_class = JwtLoginSerializer
    permission_classes = [permissions.AllowAny]


class JwtSignupView(APIView):
    """
    Register a user + organization using the same fields as the HTML signup form.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        form = serializer.form
        try:
            user, organization, member = create_user_with_organization(form)
        except IntegrityError as exc:
            raise ValidationError(self._map_integrity_error(exc)) from exc

        # Maintain compatibility with existing flows by logging the user in.
        login(request, user)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "success": True,
                "message": f'Welcome to Jadeed! Your organization "{organization.name}" has been created successfully.',
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": serialize_user(user, member=member),
            },
            status=status.HTTP_201_CREATED,
        )

    def _map_integrity_error(self, exc):
        message = str(exc)
        if "organizations_organization.name" in message:
            return {
                "organization_name": [
                    "An organization with this name already exists. Please choose a different name."
                ]
            }
        elif "organizations_organization.slug" in message:
            return {
                "organization_name": [
                    "Organization slug already exists. Please tweak the organization name."
                ]
            }
        return {
            "non_field_errors": [
                "We could not complete your signup. Please try again or contact support."
            ]
        }


class JwtLogoutView(APIView):
    """
    Blacklist a refresh token to invalidate client sessions.
    """

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {
                    "success": False,
                    "errors": {"refresh": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except (TokenError, InvalidToken):
            return Response(
                {
                    "success": False,
                    "errors": {"refresh": ["Refresh token is invalid or expired."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        member = get_user_organization_member(request.user)
        return Response(
            {
                "success": True,
                "message": "Successfully logged out.",
                "user": serialize_user(request.user, member=member),
            },
            status=status.HTTP_200_OK,
        )
