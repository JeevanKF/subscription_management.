"""
billing/views_web.py
Staff invoice list/detail pages.
"""

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from accounts.decorators import staff_required
from .models import Invoice


@staff_required
def invoice_list(request):
    qs = Invoice.objects.select_related("subscription__customer").order_by("-created_at")

    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "billing/invoice_list.html", {
        "page_obj": page_obj,
        "statuses": Invoice.Status.choices,
        "selected_status": status or "",
    })


@staff_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("subscription__customer").prefetch_related("lines", "payments"),
        pk=pk,
    )
    return render(request, "billing/invoice_detail.html", {"invoice": invoice})
