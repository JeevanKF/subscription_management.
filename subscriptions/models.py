"""
subscriptions/models.py
Subscription, SubscriptionLine — stub definitions.
"""

from django.db import models
from django.conf import settings
from products.models import Plan, Variant, TaxRule


class Subscription(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        limit_choices_to={"role": "customer"},
    )
    number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField()
    next_billing_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.number} — {self.customer}"


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, null=True, blank=True, on_delete=models.SET_NULL)
    tax_rule = models.ForeignKey(TaxRule, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.subscription.number} / {self.plan.name}"
