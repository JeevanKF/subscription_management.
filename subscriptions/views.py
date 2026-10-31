"""
subscriptions/views.py — DRF viewsets for the React frontend.

Every lifecycle action is a POST on /api/subscriptions/{id}/<action>/ and
calls the matching function in services.py. Customers only ever get their
own subscriptions in the queryset, so another customer's id is a 404.
"""

from django.db.models import Q
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import QuotationTemplate, Subscription
from .permissions import IsStaffOrAdmin
from .serializers import (
    ActionSerializer,
    FromTemplateSerializer,
    QuotationTemplateSerializer,
    StatusChangeSerializer,
    SubscriptionSerializer,
    SubscriptionWriteSerializer,
)

# Actions a customer may run on their own subscription (plan rules still apply)
CUSTOMER_ACTIONS = {"list", "retrieve", "history", "confirm", "pause", "resume", "renew", "close"}


def _error_response(exc):
    body = {exc.field: [exc.message]} if exc.field else {"detail": exc.message}
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.CreateModelMixin, mixins.UpdateModelMixin,
                          viewsets.GenericViewSet):
    """
    GET  /api/subscriptions/?search=&status=&plan=&customer=
    POST /api/subscriptions/                          create a Draft (staff)
    GET  /api/subscriptions/{id}/
    PATCH/PUT /api/subscriptions/{id}/                edit a Draft (staff)
    POST /api/subscriptions/{id}/send-quote|confirm|activate|pause|resume|renew|close/
    GET  /api/subscriptions/{id}/history/
    POST /api/subscriptions/close-expired/            run auto-close now (staff)
    """

    serializer_class = SubscriptionSerializer
    lookup_value_regex = r"\d+"

    def get_permissions(self):
        if self.action in CUSTOMER_ACTIONS:
            return [permissions.IsAuthenticated()]
        return [IsStaffOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Subscription.objects.select_related("customer", "plan")
            .prefetch_related("lines__product", "lines__variant", "lines__tax_rule")
        )
        if user.role == "customer":
            qs = qs.filter(customer=user)
        return qs

    def filter_queryset(self, queryset):
        params = self.request.query_params
        if search := params.get("search", "").strip():
            queryset = queryset.filter(
                Q(number__icontains=search) | Q(customer__name__icontains=search)
                | Q(customer__email__icontains=search)
            )
        if value := params.get("status"):
            queryset = queryset.filter(status=value)
        if value := params.get("plan"):
            queryset = queryset.filter(plan_id=value)
        if value := params.get("customer"):
            queryset = queryset.filter(customer_id=value)
        return queryset

    def list(self, request, *args, **kwargs):
        services.expire_quotations(self.get_queryset())
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        services.expire_quotation(self.get_object())
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        data = SubscriptionWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            subscription = services.create_subscription(actor=request.user, **data.validated_data)
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(self._read(subscription), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        subscription = self.get_object()
        data = SubscriptionWriteSerializer(data=request.data, partial=kwargs.get("partial", False))
        data.is_valid(raise_exception=True)
        fields = dict(data.validated_data)
        try:
            services.update_draft(subscription, actor=request.user, **fields)
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(self._read(subscription))

    def _read(self, subscription):
        return SubscriptionSerializer(self.get_queryset().get(pk=subscription.pk)).data

    def _run(self, request, func, **extra):
        subscription = self.get_object()
        try:
            func(subscription, actor=request.user, **extra)
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(self._read(subscription))

    def _input(self, request):
        data = ActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return data.validated_data

    @action(detail=True, methods=["post"], url_path="send-quote")
    def send_quote(self, request, pk=None):
        return self._run(request, services.send_quote, validity_days=self._input(request).get("validity_days"))

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._run(request, services.confirm_subscription)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        return self._run(request, services.activate_subscription)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        return self._run(request, services.pause_subscription, reason=self._input(request)["reason"])

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self._run(request, services.resume_subscription, reason=self._input(request)["reason"])

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        return self._run(request, services.renew_subscription)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._run(request, services.close_subscription, reason=self._input(request)["reason"])

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        changes = self.get_object().status_changes.select_related("changed_by")
        return Response(StatusChangeSerializer(changes, many=True).data)

    @action(detail=False, methods=["post"], url_path="close-expired")
    def close_expired(self, request):
        closed = services.close_expired_subscriptions()
        return Response({"closed": closed, "count": len(closed)})


class QuotationTemplateViewSet(viewsets.ModelViewSet):
    """
    /api/subscriptions/quotation-templates/                       list, create (staff)
    /api/subscriptions/quotation-templates/{id}/                  view, edit, delete (staff)
    POST /api/subscriptions/quotation-templates/{id}/create-subscription/
         body: {customer, start_date} → a new Draft copied from the template
    """

    serializer_class = QuotationTemplateSerializer
    permission_classes = [IsStaffOrAdmin]

    def get_queryset(self):
        qs = QuotationTemplate.objects.select_related("plan").prefetch_related("lines__product")
        if self.request.query_params.get("active") == "true":
            qs = qs.filter(is_active=True)
        return qs

    @action(detail=True, methods=["post"], url_path="create-subscription")
    def create_subscription(self, request, pk=None):
        data = FromTemplateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            subscription = services.create_from_template(self.get_object(), actor=request.user,
                                                         **data.validated_data)
        except services.SubscriptionError as exc:
            return _error_response(exc)
        return Response(SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED)
