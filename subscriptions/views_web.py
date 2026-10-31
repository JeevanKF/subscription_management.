"""
subscriptions/views_web.py
Staff list/detail pages for subscriptions, plus a CSV export of the
current filtered list.
"""

import csv

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from accounts.decorators import staff_required
from .models import Subscription

User = get_user_model()


def _filtered_queryset(request):
    qs = Subscription.objects.select_related("customer").prefetch_related("lines__plan")

    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)

    customer_id = request.GET.get("customer")
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    return qs.order_by("-created_at")


@staff_required
def subscription_list(request):
    qs = _filtered_queryset(request)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    customers = User.objects.filter(role="customer").order_by("username")

    return render(request, "subscriptions/list.html", {
        "page_obj": page_obj,
        "statuses": Subscription.Status.choices,
        "customers": customers,
        "selected_status": request.GET.get("status", ""),
        "selected_customer": request.GET.get("customer", ""),
    })


@staff_required
def subscription_detail(request, pk):
    subscription = get_object_or_404(
        Subscription.objects.select_related("customer").prefetch_related("lines__plan", "invoices"),
        pk=pk,
    )
    return render(request, "subscriptions/detail.html", {"subscription": subscription})


@staff_required
def subscription_export(request):
    """Exports the currently filtered subscription list as CSV."""
    qs = _filtered_queryset(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="subscriptions.csv"'

    writer = csv.writer(response)
    writer.writerow(["Number", "Customer", "Status", "Start date", "Next billing date"])
    for sub in qs.iterator():
        writer.writerow([
            sub.number,
            sub.customer.get_full_name() or sub.customer.username,
            sub.get_status_display(),
            sub.start_date,
            sub.next_billing_date or "",
        ])

    return response
