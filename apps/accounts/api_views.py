from django.contrib.auth import authenticate, login, logout

from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import SignUpForm
from .services import create_user_with_organization
from organizations.permissions import get_user_organization_member


def _serialize_member(member):
    if not member:
        return None
    organization = member.organization
    return {
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "is_active": organization.is_active,
        },
        "role": {
            "id": member.role.id,
            "type": member.role.role_type,
            "label": member.role.get_role_type_display(),
        },
        "department": (
            {
                "id": member.department.id,
                "name": member.department.name,
                "slug": member.department.slug,
            }
            if member.department
            else None
        ),
    }


def _serialize_user(user):
    member = get_user_organization_member(user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "member": _serialize_member(member),
    }


class ApiLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        missing = {}
        if not username:
            missing["username"] = ["This field is required."]
        if not password:
            missing["password"] = ["This field is required."]
        if missing:
            return Response(
                {"success": False, "errors": missing},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response(
                {
                    "success": False,
                    "errors": {"non_field_errors": ["Invalid username or password."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.is_active:
            return Response(
                {
                    "success": False,
                    "errors": {"non_field_errors": ["This account is inactive."]},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        login(request, user)
        token, _ = Token.objects.get_or_create(user=user)
        member = get_user_organization_member(user)
        message = (
            f"Welcome back! You are signed in as {member.role.get_role_type_display()}."
            if member
            else "Welcome back! Please complete your organization setup."
        )
        return Response(
            {
                "success": True,
                "message": message,
                "token": token.key,
                "data": _serialize_user(user),
            },
            status=status.HTTP_200_OK,
        )


class ApiLogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        logout(request)
        return Response(
            {"success": True, "message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )


class ApiSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        form = SignUpForm(request.data)
        if not form.is_valid():
            return Response(
                {"success": False, "errors": form.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, organization, _ = create_user_with_organization(form)
        login(request, user)
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": f'Account created and logged in for "{organization.name}".',
                "token": token.key,
                "data": _serialize_user(user),
            },
            status=status.HTTP_201_CREATED,
        )
