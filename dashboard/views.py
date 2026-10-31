"""
dashboard/views.py — Finance summary endpoint (admin + staff only).
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from subscriptions.models import Subscription
from billing.models import Invoice, Payment
from django.db.models import Sum, Count


def _is_staff_or_admin(user):
    return user.role in ("admin", "staff")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary(request):
    """GET /api/dashboard/ — top-level finance metrics."""
    if not _is_staff_or_admin(request.user):
        return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

    data = {
        "subscriptions": {
            "total": Subscription.objects.count(),
            "active": Subscription.objects.filter(status="active").count(),
            "paused": Subscription.objects.filter(status="paused").count(),
        },
        "invoices": {
            "total": Invoice.objects.count(),
            "overdue": Invoice.objects.filter(status="overdue").count(),
            "total_billed": Invoice.objects.aggregate(t=Sum("total"))["t"] or 0,
        },
        "payments": {
            "total_collected": Payment.objects.aggregate(t=Sum("amount"))["t"] or 0,
        },
    }
    return Response(data)
