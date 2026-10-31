"""products/urls.py"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("", views.ProductViewSet, basename="product")
router.register("plans", views.PlanViewSet, basename="plan")
router.register("tax-rules", views.TaxRuleViewSet, basename="taxrule")

urlpatterns = [path("", include(router.urls))]
