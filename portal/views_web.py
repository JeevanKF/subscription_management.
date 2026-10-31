"""
portal/views_web.py
Customer self-service pages: own subscriptions/invoices, plus the
accept/pause/close/renew actions on their own subscriptions.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import customer_required
from billing.models import Invoice
from subscriptions.models import Subscription


@customer_required
def my_subscriptions(request):
    subs = Subscription.objects.filter(customer=request.user).prefetch_related("lines__plan")
    return render(request, "portal/my_subscriptions.html", {"subscriptions": subs})


@customer_required
def my_invoices(request):
    invoices = (
        Invoice.objects.filter(subscription__customer=request.user)
        .select_related("subscription")
        .order_by("-created_at")
    )
    return render(request, "portal/my_invoices.html", {"invoices": invoices})


@customer_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.prefetch_related("lines", "payments"),
        pk=pk,
        subscription__customer=request.user,
    )
    return render(request, "portal/invoice_detail.html", {"invoice": invoice})


@customer_required
def invoice_print(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.prefetch_related("lines", "payments"),
        pk=pk,
        subscription__customer=request.user,
    )
    return render(request, "portal/invoice_print.html", {"invoice": invoice})


def _run_action(request, pk, action_name, verb):
    subscription = get_object_or_404(Subscription, pk=pk, customer=request.user)
    if request.method == "POST":
        try:
            getattr(subscription, action_name)()
            messages.success(request, f"Subscription {subscription.number} {verb}.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("portal:my_subscriptions")


@customer_required
def accept_subscription(request, pk):
    return _run_action(request, pk, "accept", "accepted")


@customer_required
def pause_subscription(request, pk):
    return _run_action(request, pk, "pause", "paused")


@customer_required
def close_subscription(request, pk):
    return _run_action(request, pk, "close", "closed")


@customer_required
def renew_subscription(request, pk):
    return _run_action(request, pk, "renew", "renewed")
