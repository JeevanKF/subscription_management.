"""
accounts/decorators.py
Role-based access control decorators for views.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def role_required(*roles):
    """Restrict a view to users whose role is in `roles`."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                return redirect("accounts:home")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def admin_required(view_func):
    return role_required("admin")(view_func)


def staff_required(view_func):
    return role_required("admin", "staff")(view_func)


def customer_required(view_func):
    return role_required("customer")(view_func)

