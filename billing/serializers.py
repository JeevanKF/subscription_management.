"""
billing/serializers.py
DRF Serializers for M3:
- InvoiceSerializer with nested lines, payments, and status history
- DiscountSerializer
- PaymentSerializer
- BillingRunSerializer
"""

from rest_framework import serializers
from billing.models import (
    Invoice,
    InvoiceLine,
    Payment,
    Discount,
    DiscountUse,
    InvoiceStatusChange,
)


class DiscountSerializer(serializers.ModelSerializer):
    is_available = serializers.BooleanField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Discount
        fields = [
            "id",
            "code",
            "name",
            "discount_type",
            "value",
            "scope",
            "product",
            "product_name",
            "usage_limit",
            "times_used",
            "valid_from",
            "valid_until",
            "is_active",
            "is_available",
            "created_at",
        ]
        read_only_fields = ["id", "times_used", "created_at"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "description",
            "quantity",
            "unit_price",
            "discount_amount",
            "tax_rate",
            "tax_amount",
            "line_total",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by.username", read_only=True)
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "invoice",
            "invoice_number",
            "amount",
            "payment_date",
            "method",
            "reference",
            "note",
            "recorded_by",
            "recorded_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at"]


class InvoiceStatusChangeSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.username", read_only=True)

    class Meta:
        model = InvoiceStatusChange
        fields = [
            "id",
            "from_status",
            "to_status",
            "changed_by_name",
            "note",
            "changed_at",
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    """Lighter serializer for fast list views."""
    customer_name = serializers.CharField(source="subscription.customer.username", read_only=True)
    customer_email = serializers.CharField(source="subscription.customer.email", read_only=True)
    subscription_number = serializers.CharField(source="subscription.number", read_only=True)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "uuid",
            "number",
            "subscription_number",
            "customer_name",
            "customer_email",
            "period_start",
            "period_end",
            "status",
            "subtotal",
            "discount_total",
            "tax_total",
            "total",
            "total_paid",
            "balance_due",
            "due_date",
            "last_reminded_date",
            "reminder_count",
            "created_at",
        ]


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer with nested lines, payments, and history."""
    customer_name = serializers.CharField(source="subscription.customer.username", read_only=True)
    customer_email = serializers.CharField(source="subscription.customer.email", read_only=True)
    subscription_number = serializers.CharField(source="subscription.number", read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    status_history = InvoiceStatusChangeSerializer(many=True, read_only=True)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "uuid",
            "number",
            "subscription_number",
            "customer_name",
            "customer_email",
            "period_start",
            "period_end",
            "status",
            "subtotal",
            "discount_total",
            "tax_total",
            "total",
            "total_paid",
            "balance_due",
            "due_date",
            "last_reminded_date",
            "reminder_count",
            "created_at",
            "lines",
            "payments",
            "status_history",
        ]


InvoiceSerializer = InvoiceDetailSerializer


class RecordPaymentRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_date = serializers.DateField()
    method = serializers.CharField(max_length=50, default="bank_transfer")
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class BillingRunRequestSerializer(serializers.Serializer):
    target_date = serializers.DateField(required=False)
    dry_run = serializers.BooleanField(default=False)
