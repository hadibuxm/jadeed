from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.forms import SignUpForm
from organizations.models import Organization


User = get_user_model()


def serialize_member(member):
    if not member:
        return None
    organization = member.organization
    role = member.role
    department = member.department
    return {
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "is_active": organization.is_active,
        },
        "role": {
            "id": role.id,
            "type": role.role_type,
            "label": role.get_role_type_display(),
        },
        "department": (
            {
                "id": department.id,
                "name": department.name,
                "slug": department.slug,
            }
            if department
            else None
        ),
    }


def serialize_user(user, member=None):
    from organizations.permissions import get_user_organization_member

    member = member or get_user_organization_member(user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "member": serialize_member(member),
    }


class JwtLoginSerializer(TokenObtainPairSerializer):
    """
    Extend SimpleJWT serializer to include serialized user details.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = serialize_user(self.user)
        return data


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    organization_name = serializers.CharField(max_length=255)
    job_title = serializers.CharField(max_length=255, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=20, allow_blank=True, required=False)

    def validate(self, attrs):
        form = SignUpForm(attrs)
        if not form.is_valid():
            raise serializers.ValidationError(form.errors)
        organization_name = form.cleaned_data.get("organization_name")
        if organization_name and Organization.objects.filter(
            name__iexact=organization_name
        ).exists():
            raise serializers.ValidationError(
                {
                    "organization_name": [
                        "An organization with this name already exists. Please choose a different name."
                    ]
                }
            )
        self.form = form
        return attrs
