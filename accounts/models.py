"""
accounts/models.py
Custom User with role field. AUTH_USER_MODEL points here.
Users log in with their email (case-insensitive), there is no username.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from .validators import validate_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)   # password=None gives an unusable password
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email):
        # Login looks users up through here, so "Asha@Example.com" finds "asha@example.com"
        return self.get(email__iexact=email)

    def normalize_email(self, email):
        return (email or "").strip().lower()


class User(AbstractUser):
    """
    Extends Django's built-in user.
    Roles: admin, staff, customer. New sign-ups are always customers.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Internal Staff"
        CUSTOMER = "customer", "Customer"

    username = None
    first_name = None
    last_name = None

    email = models.EmailField("email address", unique=True)
    name = models.CharField(max_length=150)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
    )
    company = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[validate_phone])
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        ordering = ["name", "email"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
                violation_error_message="An account with this email already exists.",
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = User.objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_staff_member(self):
        return self.role == self.Role.STAFF

    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    def __str__(self):
        return self.name or self.email
