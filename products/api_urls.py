"""products/api_urls.py — JSON API for the React frontend, mounted at /api/products/."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
# "plans" and "tax-rules" must come before "" or the product detail route swallows them
router.register("plans", api_views.PlanViewSet, basename="plan")
router.register("tax-rules", api_views.TaxRuleViewSet, basename="taxrule")
router.register("", api_views.ProductViewSet, basename="product")

urlpatterns = [path("", include(router.urls))]
