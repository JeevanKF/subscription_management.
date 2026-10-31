"""
billing/views.py
DRF Views and ViewSets for Module M3:
- InvoiceViewSet with UUID lookup, role scoping, actions (confirm, send, cancel, pay, remind)
- Billing run and preview endpoints
- DiscountViewSet (admin only for edits)
- CSV exports for invoices and payments
"""

from django.http import HttpResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from billing.models import Invoice, Discount, Payment
from billing.serializers import (
    InvoiceListSerializer,
    InvoiceDetailSerializer,
    DiscountSerializer,
    PaymentSerializer,
    RecordPaymentRequestSerializer,
    BillingRunRequestSerializer,
)
from billing.services import (
    run_billing,
    record_payment,
    confirm_invoice,
    send_invoice,
    cancel_invoice,
    send_reminder,
    export_invoices_csv,
    export_payments_csv,
)


class IsStaffOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ("admin", "staff"))


class IsAdminUserOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Invoice ViewSet:
    - Lookups use 'uuid' to avoid sequential IDOR enumeration
    - Strict server-side ownership: customers only see their own invoices
    - 404 returned if unauthorized record requested
    """
    lookup_field = "uuid"
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        return InvoiceListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related(
            "subscription__customer"
        ).prefetch_related("lines", "payments")

        # Customer scoping
        if user.role == "customer":
            qs = qs.filter(subscription__customer=user)

        # Filters: status, search, overdue
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        overdue_param = self.request.query_params.get("overdue")
        if overdue_param in ("true", "1"):
            today = timezone.localdate()
            qs = qs.filter(due_date__lt=today).exclude(status__in=[Invoice.Status.PAID, Invoice.Status.CANCELLED])

        search = self.request.query_params.get("search")
        if search:
            qs = (qs.filter(number__icontains=search)
                      | qs.filter(subscription__customer__name__icontains=search)
                      | qs.filter(subscription__customer__email__icontains=search))

        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrAdmin])
    def confirm(self, request, uuid=None):
        invoice = self.get_object()
        try:
            updated = confirm_invoice(invoice, actor=request.user)
            return Response(InvoiceDetailSerializer(updated).data)
        except ValidationError as e:
            return Response({"detail": str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrAdmin])
    def send(self, request, uuid=None):
        invoice = self.get_object()
        try:
            updated = send_invoice(invoice, actor=request.user)
            return Response(InvoiceDetailSerializer(updated).data)
        except ValidationError as e:
            return Response({"detail": str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrAdmin])
    def cancel(self, request, uuid=None):
        invoice = self.get_object()
        reason = request.data.get("reason", "")
        try:
            updated = cancel_invoice(invoice, reason=reason, actor=request.user)
            return Response(InvoiceDetailSerializer(updated).data)
        except ValidationError as e:
            return Response({"detail": str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrAdmin])
    def pay(self, request, uuid=None):
        serializer = RecordPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payment = record_payment(
                invoice_uuid=uuid,
                amount=data["amount"],
                payment_date=data["payment_date"],
                method=data.get("method", "bank_transfer"),
                reference=data.get("reference", ""),
                note=data.get("note", ""),
                recorded_by=request.user,
            )
            # Re-fetch invoice with updated status & balance
            invoice = self.get_object()
            return Response({
                "payment": PaymentSerializer(payment).data,
                "invoice": InvoiceDetailSerializer(invoice).data,
            })
        except ValidationError as e:
            return Response({"detail": str(e.message if hasattr(e, 'message') else e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsStaffOrAdmin])
    def remind(self, request, uuid=None):
        invoice = self.get_object()
        data = send_reminder(invoice, actor=request.user)
        return Response(data)

    @action(detail=False, methods=["get"], permission_classes=[IsStaffOrAdmin])
    def export(self, request):
        qs = self.get_queryset()
        csv_data = export_invoices_csv(qs)
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="invoices.csv"'
        return response


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related("invoice__subscription__customer", "recorded_by")
        if user.role == "customer":
            return qs.filter(invoice__subscription__customer=user)
        return qs.order_by("-payment_date", "-created_at")

    @action(detail=False, methods=["get"], permission_classes=[IsStaffOrAdmin])
    def export(self, request):
        qs = self.get_queryset()
        csv_data = export_payments_csv(qs)
        response = HttpResponse(csv_data, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="payments.csv"'
        return response


class DiscountViewSet(viewsets.ModelViewSet):
    queryset = Discount.objects.all().select_related("product").order_by("-created_at")
    serializer_class = DiscountSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsAdminUserOnly()]


# ─── Billing Run Views ────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsStaffOrAdmin])
def billing_preview(request):
    """GET /api/billing/run/preview/ — dry-run billing simulation."""
    target_date_str = request.query_params.get("target_date")
    target_date = None
    if target_date_str:
        try:
            target_date = timezone.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid target_date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

    result = run_billing(target_date=target_date, dry_run=True, actor=request.user)
    return Response(result)


@api_view(["POST"])
@permission_classes([IsStaffOrAdmin])
def execute_billing_run(request):
    """POST /api/billing/run/ — execute billing run with row locks and idempotency."""
    serializer = BillingRunRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    target_date = serializer.validated_data.get("target_date")
    dry_run = serializer.validated_data.get("dry_run", False)

    result = run_billing(target_date=target_date, dry_run=dry_run, actor=request.user)
    return Response(result)
