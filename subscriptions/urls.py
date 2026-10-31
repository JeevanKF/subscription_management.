"""subscriptions/urls.py — JSON API, mounted at /api/subscriptions/."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# "quotation-templates" must come before "" or the subscription detail route swallows it
router.register("quotation-templates", views.QuotationTemplateViewSet, basename="quotation-template")
router.register("", views.SubscriptionViewSet, basename="subscription")

urlpatterns = [path("", include(router.urls))]
