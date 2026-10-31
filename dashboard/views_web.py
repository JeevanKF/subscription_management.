"""
dashboard/views_web.py
Staff dashboard: top-line metrics, filterable charts, and the overdue list.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.shortcuts import render

from accounts.decorators import staff_required
from billing.models import Invoice, Payment
from products.models import Plan
from subscriptions.models import Subscription

User = get_user_model()

CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "annually": 12}


def _monthly_equivalent(line):
    months = CYCLE_MONTHS.get(line.plan.billing_cycle, 1)
    return (line.unit_price * line.quantity) / Decimal(months)


def _apply_filters(qs, request, date_field):
    start = request.GET.get("start")
    end = request.GET.get("end")
    customer_id = request.GET.get("customer")
    plan_id = request.GET.get("plan")

    if start:
        qs = qs.filter(**{f"{date_field}__gte": start})
    if end:
        qs = qs.filter(**{f"{date_field}__lte": end})
    if customer_id:
        qs = qs.filter(subscription__customer_id=customer_id)
    if plan_id:
        qs = qs.filter(subscription__lines__plan_id=plan_id)

    return qs.distinct()


@staff_required
def index(request):
    active_subs = Subscription.objects.filter(status="active").prefetch_related("lines__plan")
    mrr = sum((_monthly_equivalent(line) for sub in active_subs for line in sub.lines.all()), Decimal("0"))

    revenue_collected = Payment.objects.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    outstanding_invoices = Invoice.objects.exclude(status__in=["paid", "cancelled", "draft"])
    outstanding = sum((inv.balance_due for inv in outstanding_invoices), Decimal("0"))

    overdue_qs = _apply_filters(
        Invoice.objects.filter(status="overdue").select_related("subscription__customer"),
        request,
        "due_date",
    ).order_by("due_date")

    invoices_for_charts = _apply_filters(Invoice.objects.all(), request, "created_at")

    revenue_rows = (
        Payment.objects.values("payment_date__year", "payment_date__month")
        .annotate(total=Sum("amount"))
        .order_by("payment_date__year", "payment_date__month")
    )
    revenue_labels = [f"{row['payment_date__year']}-{row['payment_date__month']:02d}" for row in revenue_rows]
    revenue_values = [float(row["total"]) for row in revenue_rows]

    status_rows = invoices_for_charts.values("status").annotate(count=Count("id"))
    status_counts = {row["status"]: row["count"] for row in status_rows}
    status_labels = [label for _, label in Invoice.Status.choices if status_counts.get(_)]
    status_values = [status_counts[value] for value, label in Invoice.Status.choices if status_counts.get(value)]

    context = {
        "metrics": {
            "active_subscriptions": active_subs.count(),
            "mrr": mrr,
            "revenue_collected": revenue_collected,
            "outstanding": outstanding,
            "overdue_count": overdue_qs.count(),
        },
        "overdue_invoices": overdue_qs[:20],
        "revenue_labels": revenue_labels,
        "revenue_values": revenue_values,
        "status_labels": status_labels,
        "status_values": status_values,
        "customers": User.objects.filter(role="customer").order_by("username"),
        "plans": Plan.objects.select_related("product").order_by("product__name", "name"),
        "selected_start": request.GET.get("start", ""),
        "selected_end": request.GET.get("end", ""),
        "selected_customer": request.GET.get("customer", ""),
        "selected_plan": request.GET.get("plan", ""),
    }
    return render(request, "dashboard/index.html", context)
