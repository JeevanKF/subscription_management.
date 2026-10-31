"""
products/models.py
TaxRule, Product, ProductVariant, Plan.
All money fields are DecimalField(max_digits=12, decimal_places=2).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

AMOUNT_ERROR = "Enter an amount of 0 or more."
TAX_RATE_ERROR = "Tax rate must be between 0 and 100."
PLAN_PRICE_ERROR = "Price must be more than 0."
MIN_QUANTITY_ERROR = "Minimum quantity must be at least 1."
END_DATE_ERROR = "End date must be after start date."
PLAN_UNAVAILABLE_ERROR = "This plan isn't available on that date."


class TaxRule(models.Model):
    name = models.CharField(max_length=100, help_text="e.g. GST 18%")
    rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0, TAX_RATE_ERROR), MaxValueValidator(100, TAX_RATE_ERROR)],
        help_text="Percentage, e.g. 18.00 for 18%",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rate__gte=0) & Q(rate__lte=100),
                name="products_taxrule_rate_0_100",
                violation_error_message=TAX_RATE_ERROR,
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class Product(models.Model):
    class ProductType(models.TextChoices):
        SERVICE = "service", "Service"
        GOODS = "goods", "Goods"

    name = models.CharField(max_length=200)
    product_type = models.CharField(max_length=20, choices=ProductType.choices, default=ProductType.SERVICE)
    sales_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(0, AMOUNT_ERROR)],
    )
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(0, AMOUNT_ERROR)],
    )
    tax_rule = models.ForeignKey(
        TaxRule, null=True, blank=True, on_delete=models.PROTECT,
        related_name="products", verbose_name="default tax",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(sales_price__gte=0), name="products_product_sales_price_gte_0",
                                   violation_error_message=AMOUNT_ERROR),
            models.CheckConstraint(condition=Q(cost_price__gte=0), name="products_product_cost_price_gte_0",
                                   violation_error_message=AMOUNT_ERROR),
        ]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    """e.g. attribute "Brand", value "Odoo", extra_price 560.00."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute = models.CharField(max_length=100, help_text="e.g. Brand")
    value = models.CharField(max_length=100, help_text="e.g. Odoo")
    extra_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(0, AMOUNT_ERROR)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["attribute", "value"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "attribute", "value"],
                name="products_variant_unique_per_product",
                violation_error_message="This variant already exists.",
            ),
        ]

    def __str__(self):
        return f"{self.attribute}: {self.value}"


# Older code imports `Variant`; keep the name working.
Variant = ProductVariant


class PlanQuerySet(models.QuerySet):
    def available(self, on_date=None):
        """Active plans whose start/end dates include `on_date` (default: today)."""
        on_date = on_date or timezone.localdate()
        return self.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=on_date),
            Q(end_date__isnull=True) | Q(end_date__gte=on_date),
            is_active=True,
        )


class Plan(models.Model):
    class BillingPeriod(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    name = models.CharField(max_length=200)
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL, related_name="plans",
    )
    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"), PLAN_PRICE_ERROR)],
    )
    billing_period = models.CharField(max_length=10, choices=BillingPeriod.choices, default=BillingPeriod.MONTHLY)
    min_quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1, MIN_QUANTITY_ERROR)],
    )
    start_date = models.DateField(null=True, blank=True, help_text="First day the plan can be chosen.")
    end_date = models.DateField(null=True, blank=True, help_text="Last day the plan can be chosen.")
    auto_close = models.BooleanField(default=False, help_text="Close subscriptions automatically after expiry.")
    closable = models.BooleanField(default=True, help_text="Staff may close subscriptions early.")
    pausable = models.BooleanField(default=True)
    renewable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="products_plan_price_gt_0",
                                   violation_error_message=PLAN_PRICE_ERROR),
            models.CheckConstraint(condition=Q(min_quantity__gte=1), name="products_plan_min_quantity_gte_1",
                                   violation_error_message=MIN_QUANTITY_ERROR),
            models.CheckConstraint(
                condition=Q(start_date__isnull=True) | Q(end_date__isnull=True) | Q(end_date__gt=F("start_date")),
                name="products_plan_end_after_start",
                violation_error_message=END_DATE_ERROR,
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_billing_period_display()})"

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": END_DATE_ERROR})

    def is_available(self, on_date=None):
        on_date = on_date or timezone.localdate()
        return (
            self.is_active
            and (self.start_date is None or self.start_date <= on_date)
            and (self.end_date is None or on_date <= self.end_date)
        )


def validate_plan_available(plan, on_date=None):
    """Use in subscription forms: blocks plans outside their available dates."""
    if plan and not plan.is_available(on_date):
        raise ValidationError(PLAN_UNAVAILABLE_ERROR, code="plan_unavailable")
