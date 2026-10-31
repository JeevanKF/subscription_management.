"""
accounts/models.py
Custom User with role field. AUTH_USER_MODEL points here.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Extends Django's built-in user.
    Roles: admin, staff, customer.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Internal Staff"
        CUSTOMER = "customer", "Customer"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    def is_admin(self):
        return self.role == self.Role.ADMIN

    def is_staff_member(self):
        return self.role == self.Role.STAFF

    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
