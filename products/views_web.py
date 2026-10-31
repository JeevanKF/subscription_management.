"""
products/views_web.py
Staff-facing catalogue pages (read-only — products are managed via the API/admin).
"""

from django.shortcuts import render

from accounts.decorators import staff_required
from .models import Product


@staff_required
def product_list(request):
    products = Product.objects.prefetch_related("plans", "variants").order_by("name")
    return render(request, "products/list.html", {"products": products})
