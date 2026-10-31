"""subscriptions/serializers.py"""
from rest_framework import serializers
from .models import Subscription, SubscriptionLine


class SubscriptionLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionLine
        fields = "__all__"


class SubscriptionSerializer(serializers.ModelSerializer):
    lines = SubscriptionLineSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id", "number", "status", "start_date",
            "next_billing_date", "created_at", "customer", "customer_name", "lines",
        ]
        read_only_fields = ["id", "number", "created_at"]

