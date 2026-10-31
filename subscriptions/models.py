"""
subscriptions/models.py
Subscription, SubscriptionLine, QuotationTemplate, TemplateLine, SubscriptionStatusChange.

Business rules (status transitions, numbering, expiry) live in services.py.
The model methods at the bottom of Subscription are thin wrappers kept for
callers that still use them (portal pages).
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from products.models import Plan, Product, ProductVariant, TaxRule

AMOUNT_ERROR = "Enter an amount of 0 or more."
QUANTITY_ERROR = "Quantity must be at least 1."


class Subscription(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUOTATION = "quotation", "Quotation"
        CONFIRMED = "confirmed", "Confirmed"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    class PaymentTerms(models.TextChoices):
        IMMEDIATE = "immediate", "Immediate"
        NET_15 = "net_15", "15 days"
        NET_30 = "net_30", "30 days"
        NET_45 = "net_45", "45 days"

    number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        limit_choices_to={"role": "customer"},
    )
    # Required for every new subscription (services.create_subscription checks it);
    # nullable only so rows created before this field existed can migrate.
    plan = models.ForeignKey(
        Plan, null=True, on_delete=models.PROTECT, related_name="subscriptions",
    )
    template = models.ForeignKey(
        "QuotationTemplate", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="subscriptions", help_text="Template this subscription was created from, if any.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    start_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True, help_text="Last day of the subscription term.")
    quotation_expiry = models.DateField(
        null=True, blank=True, help_text="Quotation must be confirmed on or before this date.",
    )
    payment_terms = models.CharField(max_length=10, choices=PaymentTerms.choices, default=PaymentTerms.IMMEDIATE)
    next_billing_date = models.DateField(null=True, blank=True, db_index=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expiry_date"], name="subs_status_expiry_idx"),
            models.Index(fields=["status", "quotation_expiry"], name="subs_status_quote_exp_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(expiry_date__isnull=True) | Q(expiry_date__gte=models.F("start_date")),
                name="subscriptions_expiry_after_start",
                violation_error_message="Expiry date can't be before the start date.",
            ),
        ]

    def __str__(self):
        return f"{self.number} — {self.customer}"

    @property
    def total(self):
        return sum((line.amount for line in self.lines.all()), Decimal("0.00"))

    # ── Wrappers around services.py, for callers without an API request ──────
    # Each raises services.SubscriptionError (a ValueError) when not allowed.

    def accept(self, actor=None):
        """Customer accepts a quotation (same as confirm)."""
        from . import services
        return services.confirm_subscription(self, actor=actor)

    def pause(self, actor=None):
        from . import services
        return services.pause_subscription(self, actor=actor)

    def resume(self, actor=None):
        from . import services
        return services.resume_subscription(self, actor=actor)

    def renew(self, actor=None):
        from . import services
        return services.renew_subscription(self, actor=actor)

    def close(self, actor=None):
        from . import services
        return services.close_subscription(self, actor=actor)


class SubscriptionLine(models.Model):
    """One product on a subscription. Prices are copied in so later catalogue changes don't alter it."""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, null=True, on_delete=models.PROTECT, related_name="+")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    # Mirrors subscription.plan (set in save()). Billing and the dashboard read
    # line.plan, so it stays here; subscription.plan is the source of truth.
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    tax_rule = models.ForeignKey(TaxRule, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1, QUANTITY_ERROR)])
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0, AMOUNT_ERROR)],
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="subscriptions_line_quantity_gte_1",
                                   violation_error_message=QUANTITY_ERROR),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="subscriptions_line_price_gte_0",
                                   violation_error_message=AMOUNT_ERROR),
        ]

    def __str__(self):
        return f"{self.subscription.number} / {self.product or self.plan}"

    def save(self, *args, **kwargs):
        if self.subscription.plan_id:
            self.plan_id = self.subscription.plan_id
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    @property
    def tax_amount(self):
        if not self.tax_rule:
            return Decimal("0.00")
        return (self.subtotal * self.tax_rule.rate / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def amount(self):
        return self.subtotal + self.tax_amount


class QuotationTemplate(models.Model):
    """A reusable package: plan + product lines + how long the quote stays valid."""

    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="quotation_templates")
    validity_days = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1, "Validity must be at least 1 day.")],
        help_text="Days a quotation from this template stays valid after it is sent.",
    )
    duration_months = models.PositiveIntegerField(
        null=True, blank=True, help_text="Subscription term in months; empty means open-ended.",
    )
    payment_terms = models.CharField(
        max_length=10, choices=Subscription.PaymentTerms.choices, default=Subscription.PaymentTerms.IMMEDIATE,
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(validity_days__gte=1), name="subscriptions_template_validity_gte_1",
                                   violation_error_message="Validity must be at least 1 day."),
        ]

    def __str__(self):
        return self.name


class TemplateLine(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1, QUANTITY_ERROR)])
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0, AMOUNT_ERROR)],
        help_text="Leave empty to use the price at the time the subscription is created.",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="subscriptions_tline_quantity_gte_1",
                                   violation_error_message=QUANTITY_ERROR),
        ]

    def __str__(self):
        return f"{self.template.name} / {self.product}"


class SubscriptionStatusChange(models.Model):
    """Audit trail: one row per successful status change."""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="status_changes")
    from_status = models.CharField(max_length=10, choices=Subscription.Status.choices, blank=True)
    to_status = models.CharField(max_length=10, choices=Subscription.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Empty when the system made the change (expiry, auto-close).",
    )
    reason = models.CharField(max_length=255, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at", "id"]
        indexes = [models.Index(fields=["subscription", "changed_at"], name="subs_status_change_idx")]

    def __str__(self):
        return f"{self.subscription.number}: {self.from_status or '—'} → {self.to_status}"
