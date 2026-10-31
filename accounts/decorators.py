"""
accounts/decorators.py
Role-based access control decorators for views.

    @role_required("admin")            # admin only
    @role_required("admin", "staff")   # admin or staff

Anonymous users are sent to the login page; logged-in users with the wrong
role get a 403 page.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restrict a view to users whose role is in `roles`."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def admin_required(view_func):
    return role_required("admin")(view_func)


def staff_required(view_func):
    return role_required("admin", "staff")(view_func)


def customer_required(view_func):
    return role_required("customer")(view_func)
