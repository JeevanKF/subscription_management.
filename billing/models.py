"""
billing/models.py
Models for M3: Discount, Invoice, InvoiceLine, DiscountUse, Payment, InvoiceStatusChange.
Implements:
- UUID for un-guessable API/URL lookups (IDOR defense-in-depth)
- Sequential number (e.g. INV-0001) for accounting/tax compliance
- Partial unique constraint: (subscription, period_start) WHERE status != 'cancelled'
- Check constraint: times_used <= usage_limit
"""

import uuid
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Q, F
from django.conf import settings
from django.utils import timezone
from subscriptions.models import Subscription


class Discount(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percentage (%)"
        FIXED = "fixed", "Fixed Amount (₹)"

    class Scope(models.TextChoices):
        ALL = "all", "All Subscriptions"
        SPECIFIC_PRODUCT = "specific_product", "Specific Product"
        SUBSCRIPTION = "subscription", "Specific Subscription"

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=150, blank=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.ALL)
    product = models.ForeignKey(
        "products.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="discounts",
    )
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Null for unlimited")
    times_used = models.PositiveIntegerField(default=0)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(usage_limit__isnull=True) | Q(times_used__lte=F("usage_limit")),
                name="discount_usage_limit_check",
            )
        ]

    def __str__(self):
        symbol = "%" if self.discount_type == self.DiscountType.PERCENT else "₹"
        return f"{self.code} ({self.value}{symbol})"

    @property
    def is_available(self):
        if not self.is_active:
            return False
        if self.usage_limit is not None and self.times_used >= self.usage_limit:
            return False
        return True


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        SENT = "sent", "Sent"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        CANCELLED = "cancelled", "Cancelled"

    # UUID for public/API routing — stops IDOR enumeration attacks
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    # Sequential identifier for legal, tax & accounting compliance
    number = models.CharField(max_length=30, unique=True, db_index=True)

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    due_date = models.DateField(null=True, blank=True, db_index=True)

    # Overdue reminder tracking
    last_reminded_date = models.DateField(null=True, blank=True)
    reminder_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["subscription", "period_start"]),
        ]
        constraints = [
            # Partial unique index: allows re-billing if an existing invoice was cancelled
            models.UniqueConstraint(
                fields=["subscription", "period_start"],
                condition=~Q(status="cancelled"),
                name="unique_active_subscription_period",
            )
        ]

    def __str__(self):
        return f"{self.number} ({self.get_status_display()})"

    @property
    def total_paid(self):
        paid = self.payments.aggregate(t=Sum("amount"))["t"]
        return paid or Decimal("0.00")

    @property
    def balance_due(self):
        rem = self.total - self.total_paid
        return rem if rem > Decimal("0.00") else Decimal("0.00")


class InvoiceLine(models.Model):
    """Frozen snapshot of a subscription plan/product line at billing time."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.invoice.number}: {self.description}"


class DiscountUse(models.Model):
    """Audit log of discounts applied to invoices."""
    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, related_name="uses")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="discount_uses")
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="discount_uses")
    amount_saved = models.DecimalField(max_digits=12, decimal_places=2)
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.discount.code} saved ₹{self.amount_saved} on {self.invoice.number}"


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(db_index=True)
    method = models.CharField(max_length=50, default="bank_transfer")
    reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"Payment ₹{self.amount} on {self.payment_date} ({self.invoice.number})"


class InvoiceStatusChange(models.Model):
    """Audit history for every status transition on an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=15)
    to_status = models.CharField(max_length=15)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.invoice.number}: {self.from_status} → {self.to_status} at {self.changed_at}"
