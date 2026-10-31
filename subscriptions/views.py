"""subscriptions/views.py — DRF viewset."""
from rest_framework import viewsets, permissions
from .models import Subscription
from .serializers import SubscriptionSerializer


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Subscription.objects.select_related("customer").prefetch_related("lines")
        # Customers see only their own subscriptions
        if user.role == "customer":
            return qs.filter(customer=user)
        return qs
