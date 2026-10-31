"""
subscriptions/views_web.py
Staff list/detail pages for subscriptions, plus a CSV export of the
current filtered list.
"""

import csv

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from products.models import Plan
from . import services
from .models import Subscription

Status = Subscription.Status

# Staff buttons on the detail page: (action, label, css, statuses it shows for, service)
ACTIONS = [
    ("send-quote", "Send quote", "btn-primary", (Status.DRAFT,), services.send_quote),
    ("confirm", "Confirm", "btn-primary", (Status.QUOTATION,), services.confirm_subscription),
    ("activate", "Activate", "btn-success", (Status.CONFIRMED,), services.activate_subscription),
    ("pause", "Pause", "btn-outline-warning", (Status.ACTIVE,), services.pause_subscription),
    ("resume", "Resume", "btn-success", (Status.PAUSED,), services.resume_subscription),
    ("renew", "Renew", "btn-outline-primary", (Status.ACTIVE, Status.CLOSED), services.renew_subscription),
    ("close", "Close", "btn-outline-danger",
     (Status.DRAFT, Status.QUOTATION, Status.CONFIRMED, Status.ACTIVE, Status.PAUSED), services.close_subscription),
]
ACTION_FUNCS = {name: func for name, _, _, _, func in ACTIONS}

User = get_user_model()


def _filtered_queryset(request):
    qs = Subscription.objects.select_related("customer", "plan")

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(Q(number__icontains=search) | Q(customer__name__icontains=search)
                       | Q(customer__email__icontains=search))

    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)

    plan_id = request.GET.get("plan")
    if plan_id:
        qs = qs.filter(plan_id=plan_id)

    customer_id = request.GET.get("customer")
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    return qs.order_by("-created_at")


@staff_required
def subscription_list(request):
    qs = _filtered_queryset(request)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    customers = User.objects.filter(role="customer").order_by("name", "email")

    return render(request, "subscriptions/list.html", {
        "page_obj": page_obj,
        "statuses": Subscription.Status.choices,
        "customers": customers,
        "selected_status": request.GET.get("status", ""),
        "selected_customer": request.GET.get("customer", ""),
        "plans": Plan.objects.order_by("name"),
        "selected_plan": request.GET.get("plan", ""),
        "search": request.GET.get("q", ""),
    })


@staff_required
def subscription_detail(request, pk):
    subscription = get_object_or_404(
        Subscription.objects.select_related("customer", "plan").prefetch_related("lines__product", "lines__variant", "lines__tax_rule", "invoices", "status_changes__changed_by"),
        pk=pk,
    )
    services.expire_quotation(subscription)
    # Buttons are only a hint; services.py rejects anything the plan doesn't allow
    actions = [(name, label, css) for name, label, css, statuses, _ in ACTIONS if subscription.status in statuses]
    return render(request, "subscriptions/detail.html", {"subscription": subscription, "actions": actions})


@staff_required
@require_POST
def subscription_action(request, pk, action):
    subscription = get_object_or_404(Subscription, pk=pk)
    func = ACTION_FUNCS.get(action)
    if func is None:
        messages.error(request, "Unknown action.")
    else:
        try:
            func(subscription, actor=request.user)
            messages.success(request, f"{subscription.number} is now {subscription.get_status_display().lower()}.")
        except services.SubscriptionError as exc:
            messages.error(request, exc.message)
    return redirect("subscriptions:detail", pk=pk)


@staff_required
def subscription_export(request):
    """Exports the currently filtered subscription list as CSV."""
    qs = _filtered_queryset(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="subscriptions.csv"'

    writer = csv.writer(response)
    writer.writerow(["Number", "Customer", "Plan", "Status", "Start date", "Expiry date", "Next billing date"])
    for sub in qs.iterator(chunk_size=500):
        writer.writerow([
            sub.number,
            sub.customer.name or sub.customer.email,
            sub.plan.name if sub.plan else "",
            sub.get_status_display(),
            sub.start_date,
            sub.expiry_date or "",
            sub.next_billing_date or "",
        ])

    return response
