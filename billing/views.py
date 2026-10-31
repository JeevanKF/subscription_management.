"""billing/views.py — DRF viewsets."""
from rest_framework import viewsets, permissions
from .models import Invoice, Discount
from .serializers import InvoiceSerializer, DiscountSerializer


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related("subscription__customer").prefetch_related("lines", "payments")
        if user.role == "customer":
            return qs.filter(subscription__customer=user)
        return qs


class DiscountViewSet(viewsets.ModelViewSet):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer
    permission_classes = [permissions.IsAuthenticated]
