"""subscriptions/web_urls.py — staff subscription pages, namespace: subscriptions"""

from django.urls import path

from . import views_web

app_name = "subscriptions"

urlpatterns = [
    path("", views_web.subscription_list, name="list"),
    path("export/", views_web.subscription_export, name="export"),
    path("<int:pk>/", views_web.subscription_detail, name="detail"),
]
