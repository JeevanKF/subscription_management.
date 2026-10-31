"""
billing/context_processors.py
Makes the overdue invoice count available to every template, for the
staff navbar badge.
"""

from .models import Invoice


def overdue_count(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or user.role not in ("admin", "staff"):
        return {}

    return {"overdue_invoice_count": Invoice.objects.filter(status="overdue").count()}
