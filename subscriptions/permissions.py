"""subscriptions/permissions.py — DRF permission classes for the subscription API."""
from rest_framework import permissions


class IsStaffOrAdmin(permissions.BasePermission):
    message = "Only staff and admins can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ("admin", "staff"))
