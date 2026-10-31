"""billing/web_urls.py — staff invoice pages, namespace: billing"""

from django.urls import path

from . import views_web

app_name = "billing"

urlpatterns = [
    path("invoices/", views_web.invoice_list, name="invoice_list"),
    path("invoices/<int:pk>/", views_web.invoice_detail, name="invoice_detail"),
]
