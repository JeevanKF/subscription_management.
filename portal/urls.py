"""portal/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    path("subscriptions/", views.my_subscriptions, name="portal_subscriptions"),
    path("invoices/",      views.my_invoices,      name="portal_invoices"),
]
