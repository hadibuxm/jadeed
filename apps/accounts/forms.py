from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model


User = get_user_model()


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-control").strip()
        # Placeholders for UX
        self.fields["username"].widget.attrs.setdefault("placeholder", "Username")
        self.fields["email"].widget.attrs.setdefault("placeholder", "Email (optional)")
        self.fields["password1"].widget.attrs.setdefault("placeholder", "Password")
        self.fields["password2"].widget.attrs.setdefault("placeholder", "Confirm password")


class BootstrapAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " form-control").strip()
        self.fields["username"].widget.attrs.setdefault("placeholder", "Username")
        self.fields["password"].widget.attrs.setdefault("placeholder", "Password")
