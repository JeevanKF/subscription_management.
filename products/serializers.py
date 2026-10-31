"""products/serializers.py"""
from rest_framework import serializers
from .models import Product, ProductVariant, Plan, TaxRule


class TaxRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = "__all__"


class VariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = "__all__"


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class ProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True, read_only=True)
    plans = PlanSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "product_type", "sales_price", "cost_price", "tax_rule",
            "notes", "is_active", "created_at", "variants", "plans",
        ]
