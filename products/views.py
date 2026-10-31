"""products/views.py — DRF viewsets."""
from rest_framework import viewsets, permissions
from .models import Product, Plan, TaxRule
from .serializers import ProductSerializer, PlanSerializer, TaxRuleSerializer


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_active=True).prefetch_related("variants", "plans")
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.filter(is_active=True).select_related("product")
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated]


class TaxRuleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TaxRule.objects.filter(is_active=True)
    serializer_class = TaxRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
