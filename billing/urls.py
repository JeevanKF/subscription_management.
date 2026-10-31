"""billing/urls.py"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("invoices",  views.InvoiceViewSet,  basename="invoice")
router.register("discounts", views.DiscountViewSet, basename="discount")

urlpatterns = [path("", include(router.urls))]
