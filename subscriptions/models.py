"""
subscriptions/models.py
Subscription, SubscriptionLine — stub definitions.
"""

from datetime import date

from dateutil.relativedelta import relativedelta
from django.db import models
from django.conf import settings
from products.models import Plan, Variant, TaxRule

CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "annually": 12}


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

    def _cycle_months(self):
        first_line = self.lines.select_related("plan").first()
        cycle = first_line.plan.billing_cycle if first_line else Plan.BillingCycle.MONTHLY
        return CYCLE_MONTHS.get(cycle, 1)

    def accept(self):
        """Customer accepts a draft quotation — activates the subscription."""
        if self.status != self.Status.DRAFT:
            raise ValueError("Only a draft subscription can be accepted.")
        self.status = self.Status.ACTIVE
        if not self.next_billing_date:
            self.next_billing_date = self.start_date + relativedelta(months=self._cycle_months())
        self.save(update_fields=["status", "next_billing_date", "updated_at"])

    def pause(self):
        if self.status != self.Status.ACTIVE:
            raise ValueError("Only an active subscription can be paused.")
        self.status = self.Status.PAUSED
        self.save(update_fields=["status", "updated_at"])

    def close(self):
        if self.status not in (self.Status.ACTIVE, self.Status.PAUSED):
            raise ValueError("Only an active or paused subscription can be closed.")
        self.status = self.Status.CLOSED
        self.save(update_fields=["status", "updated_at"])

    def renew(self):
        """Reactivates a paused/closed subscription and rolls billing forward."""
        if self.status not in (self.Status.PAUSED, self.Status.CLOSED):
            raise ValueError("Only a paused or closed subscription can be renewed.")
        self.status = self.Status.ACTIVE
        self.next_billing_date = date.today() + relativedelta(months=self._cycle_months())
        self.save(update_fields=["status", "next_billing_date", "updated_at"])


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, null=True, blank=True, on_delete=models.SET_NULL)
    tax_rule = models.ForeignKey(TaxRule, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.subscription.number} / {self.plan.name}"
