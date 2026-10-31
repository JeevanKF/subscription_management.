"""
accounts/forms.py
Bootstrap-friendly forms for the template-rendered auth pages.
"""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import User


def _style(form, placeholders=None):
    """Add Bootstrap's form-control class to every field widget."""
    placeholders = placeholders or {}
    for name, field in form.fields.items():
        css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
        field.widget.attrs.update({"class": css, "placeholder": placeholders.get(name, "")})
    return form


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, {"username": "Username", "password": "Password"})


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, {"email": "you@example.com"})


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class SignUpForm(UserCreationForm):
    """Public sign-up — always creates a customer, never staff/admin."""

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CUSTOMER
        if commit:
            user.save()
        return user
