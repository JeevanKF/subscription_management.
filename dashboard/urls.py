"""dashboard/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.summary, name="dashboard_summary"),
]
