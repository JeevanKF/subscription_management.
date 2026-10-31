"""
billing/urls.py
Router and explicit endpoints for M3.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from billing import views

router = DefaultRouter()
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("discounts", views.DiscountViewSet, basename="discount")

urlpatterns = [
    # Billing run actions
    path("run/preview/", views.billing_preview, name="billing_preview"),
    path("run/", views.execute_billing_run, name="execute_billing_run"),
    # ViewSet routes
    path("", include(router.urls)),
]
