"""portal/web_urls.py — customer self-service pages, namespace: portal"""

from django.urls import path

from . import views_web

app_name = "portal"

urlpatterns = [
    path("subscriptions/", views_web.my_subscriptions, name="my_subscriptions"),
    path("subscriptions/<int:pk>/accept/", views_web.accept_subscription, name="accept_subscription"),
    path("subscriptions/<int:pk>/pause/", views_web.pause_subscription, name="pause_subscription"),
    path("subscriptions/<int:pk>/resume/", views_web.resume_subscription, name="resume_subscription"),
    path("subscriptions/<int:pk>/close/", views_web.close_subscription, name="close_subscription"),
    path("subscriptions/<int:pk>/renew/", views_web.renew_subscription, name="renew_subscription"),
    path("invoices/", views_web.my_invoices, name="my_invoices"),
    path("invoices/<int:pk>/", views_web.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/print/", views_web.invoice_print, name="invoice_print"),
]
