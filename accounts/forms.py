"""
accounts/forms.py
Sign-up, login, staff creation and customer forms.
"""

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm

from .models import User
from .validators import StrongPasswordValidator

EMAIL_TAKEN = "An account with this email already exists."


class BootstrapFormMixin:
    """Adds Bootstrap 5 CSS classes to every widget. Other apps' forms can use it too."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


def _check_email_free(email, exclude_pk=None):
    email = User.objects.normalize_email(email)
    taken = User.objects.filter(email__iexact=email)
    if exclude_pk:
        taken = taken.exclude(pk=exclude_pk)
    if taken.exists():
        raise forms.ValidationError(EMAIL_TAKEN)
    return email


class NewUserForm(BootstrapFormMixin, forms.ModelForm):
    """Name, email, password and confirmation. Subclasses decide the role."""

    role = User.Role.CUSTOMER

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=StrongPasswordValidator().get_help_text(),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["name", "email"]

    def clean_email(self):
        return _check_email_free(self.cleaned_data["email"])

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1:
            try:
                password_validation.validate_password(p1, self.instance)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords don't match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.role
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class SignUpForm(NewUserForm):
    """Public sign-up. The role field never appears here: sign-ups are always customers."""
    role = User.Role.CUSTOMER


class StaffCreateForm(NewUserForm):
    """Admin-only page for creating internal staff accounts."""
    role = User.Role.STAFF

    class Meta(NewUserForm.Meta):
        fields = ["name", "email", "phone"]


class EmailLoginForm(BootstrapFormMixin, AuthenticationForm):
    """Django's login form, with the username box labelled Email."""

    error_messages = {
        "invalid_login": "Incorrect email or password.",
        "inactive": "This account is inactive.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.update({"autofocus": True, "autocomplete": "email"})


class ResetPasswordForm(BootstrapFormMixin, PasswordResetForm):
    pass


class NewPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    """Staff and admins create and edit customers. New customers set their own password by email link."""

    class Meta:
        model = User
        fields = ["name", "email", "company", "phone", "address", "is_active"]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}
        labels = {"is_active": "Active (can log in)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            del self.fields["is_active"]

    def clean_email(self):
        return _check_email_free(self.cleaned_data["email"], exclude_pk=self.instance.pk)

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.pk:
            user.role = User.Role.CUSTOMER
            user.set_unusable_password()
        if commit:
            user.save()
        return user
