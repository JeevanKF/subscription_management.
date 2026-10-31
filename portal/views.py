"""
portal/views.py — Customer-facing read-only endpoints.
Customers see only their own data; 404 for anything else.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from subscriptions.models import Subscription
from subscriptions.serializers import SubscriptionSerializer
from billing.models import Invoice
from billing.serializers import InvoiceSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscriptions(request):
    subs = Subscription.objects.filter(customer=request.user).prefetch_related("lines")
    return Response(SubscriptionSerializer(subs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_invoices(request):
    invoices = Invoice.objects.filter(
        subscription__customer=request.user
    ).prefetch_related("lines", "payments").order_by("-created_at")
    return Response(InvoiceSerializer(invoices, many=True).data)
