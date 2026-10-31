"""products/urls.py — server-rendered pages, mounted at /products/. The JSON API is in api_urls.py."""
from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("new/", views.product_create, name="product_create"),
    path("<int:pk>/", views.product_detail, name="product_detail"),
    path("<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("<int:pk>/delete/", views.product_delete, name="product_delete"),

    path("plans/", views.plan_list, name="plan_list"),
    path("plans/new/", views.plan_create, name="plan_create"),
    path("plans/<int:pk>/", views.plan_detail, name="plan_detail"),
    path("plans/<int:pk>/edit/", views.plan_edit, name="plan_edit"),
    path("plans/<int:pk>/delete/", views.plan_delete, name="plan_delete"),

    path("taxes/", views.tax_list, name="tax_list"),
    path("taxes/new/", views.tax_create, name="tax_create"),
    path("taxes/<int:pk>/edit/", views.tax_edit, name="tax_edit"),
    path("taxes/<int:pk>/delete/", views.tax_delete, name="tax_delete"),
]
