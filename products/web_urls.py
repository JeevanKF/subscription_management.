"""products/web_urls.py — staff catalogue pages, namespace: products"""

from django.urls import path

from . import views_web

app_name = "products"

urlpatterns = [
    path("", views_web.product_list, name="list"),
]
