"""
accounts/validators.py
The password rule lives here, registered in AUTH_PASSWORD_VALIDATORS, so
sign-up, staff creation and password reset all use it.
"""

import re

from django.core.exceptions import ValidationError

PASSWORD_ERROR = "Password needs 9+ characters with upper, lower and a special character."


class StrongPasswordValidator:
    """More than 8 characters, with at least one uppercase, one lowercase and one special character."""

    def validate(self, password, user=None):
        if (len(password) <= 8
                or not re.search(r"[A-Z]", password)
                or not re.search(r"[a-z]", password)
                or not re.search(r"[^A-Za-z0-9]", password)):
            raise ValidationError(PASSWORD_ERROR, code="password_too_weak")

    def get_help_text(self):
        return "More than 8 characters, with uppercase, lowercase and a special character."


def validate_phone(value):
    """Optional phone: digits, spaces and +, with 7 to 15 digits."""
    if not value:
        return
    digits = re.sub(r"\D", "", value)
    if not re.fullmatch(r"[\d +]+", value) or not 7 <= len(digits) <= 15:
        raise ValidationError("Enter a valid phone number.", code="invalid_phone")
