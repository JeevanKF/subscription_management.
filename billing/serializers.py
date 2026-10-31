"""billing/serializers.py"""
from rest_framework import serializers
from .models import Invoice, InvoiceLine, Payment, Discount


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = "__all__"


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "number", "subscription", "period_start", "period_end",
            "status", "subtotal", "tax_total", "total", "due_date",
            "created_at", "balance_due", "lines", "payments",
        ]
        read_only_fields = ["id", "number", "created_at", "balance_due"]


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = "__all__"

