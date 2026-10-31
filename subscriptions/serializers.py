"""
subscriptions/serializers.py
Read serializers return everything the React pages need in one response.
Write serializers only validate input shape; the business rules run in services.py.
"""

from django.db import transaction
from rest_framework import serializers

from accounts.models import User
from products.models import Plan, Product, ProductVariant, TaxRule

from .models import QuotationTemplate, Subscription, SubscriptionLine, SubscriptionStatusChange, TemplateLine


# ─── Subscriptions: read ──────────────────────────────────────────────────────

class SubscriptionLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default="")
    variant_name = serializers.CharField(source="variant.__str__", read_only=True, default="")
    tax_rate = serializers.DecimalField(source="tax_rule.rate", max_digits=5, decimal_places=2,
                                        read_only=True, default=None)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SubscriptionLine
        fields = [
            "id", "product", "product_name", "variant", "variant_name", "plan", "quantity",
            "unit_price", "tax_rule", "tax_rate", "subtotal", "tax_amount", "amount",
        ]


class PlanSummarySerializer(serializers.ModelSerializer):
    """The plan rules the frontend needs to decide which buttons to show (the backend still decides)."""

    class Meta:
        model = Plan
        fields = ["id", "name", "price", "billing_period", "min_quantity",
                  "pausable", "renewable", "closable", "auto_close"]


class SubscriptionSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    plan_detail = PlanSummarySerializer(source="plan", read_only=True)
    lines = SubscriptionLineSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id", "number", "status", "status_display", "customer", "customer_name", "customer_email",
            "plan", "plan_detail", "template", "start_date", "expiry_date", "quotation_expiry",
            "payment_terms", "next_billing_date", "notes", "lines", "total", "created_at", "updated_at",
        ]
        read_only_fields = fields


class StatusChangeSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.name", read_only=True, default="System")

    class Meta:
        model = SubscriptionStatusChange
        fields = ["id", "from_status", "to_status", "changed_by", "changed_by_name", "reason", "changed_at"]


# ─── Subscriptions: write ─────────────────────────────────────────────────────

class LineInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all(),
                                                 required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0,
                                          required=False, allow_null=True)
    tax_rule = serializers.PrimaryKeyRelatedField(queryset=TaxRule.objects.filter(is_active=True),
                                                  required=False, allow_null=True)


class SubscriptionWriteSerializer(serializers.Serializer):
    """Input for create (all fields) and draft edits (partial)."""

    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.CUSTOMER))
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    start_date = serializers.DateField()
    expiry_date = serializers.DateField(required=False, allow_null=True)
    payment_terms = serializers.ChoiceField(choices=Subscription.PaymentTerms.choices,
                                            default=Subscription.PaymentTerms.IMMEDIATE)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = LineInputSerializer(many=True)


class ActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    validity_days = serializers.IntegerField(required=False, min_value=1, allow_null=True)


# ─── Quotation templates ──────────────────────────────────────────────────────

class TemplateLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = TemplateLine
        fields = ["id", "product", "product_name", "variant", "quantity", "unit_price"]

    def validate(self, attrs):
        variant, product = attrs.get("variant"), attrs.get("product")
        if variant and product and variant.product_id != product.pk:
            raise serializers.ValidationError({"variant": f"{variant} doesn't belong to {product}."})
        return attrs


class QuotationTemplateSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    lines = TemplateLineSerializer(many=True)

    class Meta:
        model = QuotationTemplate
        fields = [
            "id", "name", "plan", "plan_name", "validity_days", "duration_months", "payment_terms",
            "notes", "is_active", "lines", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        plan = attrs.get("plan") or getattr(self.instance, "plan", None)
        lines = attrs.get("lines")
        if lines is not None:
            if not lines:
                raise serializers.ValidationError({"lines": "Add at least one product line."})
            for line in lines:
                if line["quantity"] < plan.min_quantity:
                    raise serializers.ValidationError(
                        {"lines": f"{plan.name} needs a quantity of at least {plan.min_quantity}."}
                    )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines")
        template = QuotationTemplate.objects.create(**validated_data)
        TemplateLine.objects.bulk_create([TemplateLine(template=template, **line) for line in lines])
        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        instance = super().update(instance, validated_data)
        if lines is not None:
            instance.lines.all().delete()
            TemplateLine.objects.bulk_create([TemplateLine(template=instance, **line) for line in lines])
        return instance


class FromTemplateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.CUSTOMER))
    start_date = serializers.DateField()
