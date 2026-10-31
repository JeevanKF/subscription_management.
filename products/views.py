"""
products/views.py
Pages for tax rules, products (with inline variants) and plans.
Admins create, edit and delete; staff can only view.
The JSON API for the React frontend lives in api_views.py.
"""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import role_required

from .forms import PlanForm, ProductForm, TaxRuleForm, VariantFormSet
from .models import Plan, Product, TaxRule

PAGE_SIZE = 25


def _page(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))


def _delete(request, obj, label, list_url, cancel_url):
    """Shared confirm-then-delete flow. Things still in use are protected."""
    if request.method == "POST":
        try:
            obj.delete()
        except ProtectedError:
            messages.error(request, f"Can't delete this {label}: it is still in use. Mark it inactive instead.")
            return redirect(cancel_url)
        messages.success(request, f"{label.capitalize()} deleted.")
        return redirect(list_url)
    return render(request, "products/confirm_delete.html", {
        "object": obj, "label": label, "cancel_url": cancel_url,
    })


# ── Tax rules ─────────────────────────────────────────────────────────────────

@role_required("admin", "staff")
def tax_list(request):
    return render(request, "products/tax_list.html", {"page": _page(request, TaxRule.objects.all())})


@role_required("admin")
def tax_create(request):
    return _tax_form(request, TaxRule())


@role_required("admin")
def tax_edit(request, pk):
    return _tax_form(request, get_object_or_404(TaxRule, pk=pk))


def _tax_form(request, tax):
    form = TaxRuleForm(request.POST or None, instance=tax)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tax rule saved.")
        return redirect("products:tax_list")
    return render(request, "products/tax_form.html", {"form": form, "tax": tax})


@role_required("admin")
def tax_delete(request, pk):
    tax = get_object_or_404(TaxRule, pk=pk)
    return _delete(request, tax, "tax rule", "products:tax_list", reverse("products:tax_list"))


# ── Products ──────────────────────────────────────────────────────────────────

@role_required("admin", "staff")
def product_list(request):
    products = Product.objects.select_related("tax_rule").annotate(variant_count=Count("variants")).order_by("name")
    q = request.GET.get("q", "").strip()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(notes__icontains=q))
    return render(request, "products/product_list.html", {"page": _page(request, products), "q": q})


@role_required("admin", "staff")
def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related("tax_rule"), pk=pk)
    return render(request, "products/product_detail.html", {
        "product": product,
        "variants": product.variants.all(),
        "plans": product.plans.all(),
    })


@role_required("admin")
def product_create(request):
    return _product_form(request, Product())


@role_required("admin")
def product_edit(request, pk):
    return _product_form(request, get_object_or_404(Product, pk=pk))


def _product_form(request, product):
    form = ProductForm(request.POST or None, instance=product)
    formset = VariantFormSet(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            product = form.save()
            formset.instance = product
            formset.save()
        messages.success(request, "Product saved.")
        return redirect("products:product_detail", pk=product.pk)
    return render(request, "products/product_form.html", {
        "form": form, "formset": formset, "product": product,
    })


@role_required("admin")
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return _delete(request, product, "product", "products:list",
                   reverse("products:product_detail", args=[product.pk]))


# ── Plans ─────────────────────────────────────────────────────────────────────

@role_required("admin", "staff")
def plan_list(request):
    plans = Plan.objects.select_related("product")
    return render(request, "products/plan_list.html", {"page": _page(request, plans)})


@role_required("admin", "staff")
def plan_detail(request, pk):
    plan = get_object_or_404(Plan.objects.select_related("product"), pk=pk)
    return render(request, "products/plan_detail.html", {"plan": plan})


@role_required("admin")
def plan_create(request):
    return _plan_form(request, Plan())


@role_required("admin")
def plan_edit(request, pk):
    return _plan_form(request, get_object_or_404(Plan, pk=pk))


def _plan_form(request, plan):
    form = PlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        messages.success(request, "Plan saved.")
        return redirect("products:plan_detail", pk=plan.pk)
    return render(request, "products/plan_form.html", {"form": form, "plan": plan})


@role_required("admin")
def plan_delete(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    return _delete(request, plan, "plan", "products:plan_list",
                   reverse("products:plan_detail", args=[plan.pk]))
