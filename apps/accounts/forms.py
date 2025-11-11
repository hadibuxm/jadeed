from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model


User = get_user_model()


class SignUpForm(UserCreationForm):
    # User fields
    email = forms.EmailField(
        required=True,
        help_text="Required. This will be your organization's contact email."
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        help_text="Optional"
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        help_text="Optional"
    )

    # Organization fields
    organization_name = forms.CharField(
        max_length=255,
        required=True,
        help_text="Your company or organization name"
    )
    job_title = forms.CharField(
        max_length=255,
        required=False,
        initial="Owner",
        help_text="Your role in the organization"
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        help_text="Organization phone number (optional)"
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-control").strip()

        # Placeholders for UX
        self.fields["username"].widget.attrs.setdefault("placeholder", "Username")
        self.fields["email"].widget.attrs.setdefault("placeholder", "you@example.com")
        self.fields["first_name"].widget.attrs.setdefault("placeholder", "First name")
        self.fields["last_name"].widget.attrs.setdefault("placeholder", "Last name")
        self.fields["password1"].widget.attrs.setdefault("placeholder", "Password")
        self.fields["password2"].widget.attrs.setdefault("placeholder", "Confirm password")
        self.fields["organization_name"].widget.attrs.setdefault("placeholder", "Acme Corporation")
        self.fields["job_title"].widget.attrs.setdefault("placeholder", "Owner")
        self.fields["phone"].widget.attrs.setdefault("placeholder", "+1 (555) 123-4567")


class BootstrapAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-control").strip()
        self.fields["username"].widget.attrs.setdefault("placeholder", "Username")
        self.fields["password"].widget.attrs.setdefault("placeholder", "Password")
