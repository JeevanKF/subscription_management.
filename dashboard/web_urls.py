"""dashboard/web_urls.py — staff dashboard page, namespace: dashboard"""

from django.urls import path

from . import views_web

app_name = "dashboard"

urlpatterns = [
    path("", views_web.index, name="index"),
]
