"""
billing/services.py
Core business services for Module M3:
- Month-end safe billing period maths (python-dateutil relativedelta)
- Sequential number generator (INV-YYYY-0001)
- Exact calculation pipeline: Line subtotal -> product discount -> subscription discount -> tax -> rounding
- Idempotent run_billing engine with row-locking and dry-run support
- Payment recording with overpayment validation & automatic status transitions
- Status transition actions & overdue reminder logger
- CSV streaming helpers
"""

import csv
import io
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.core.exceptions import ValidationError

from billing.models import (
    Invoice,
    InvoiceLine,
    Payment,
    Discount,
    DiscountUse,
    InvoiceStatusChange,
)
from subscriptions.models import Subscription


TWO_PLACES = Decimal("0.01")


def round_curr(amount: Decimal) -> Decimal:
    """Round to 2 decimal places using standard ROUND_HALF_UP."""
    return Decimal(str(amount)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ─── 1. Date Maths ────────────────────────────────────────────────────────────

def calculate_period(start_date: date, billing_cycle: str) -> tuple[date, date, date]:
    """
    Given a period start date and billing cycle, compute:
    (period_start, period_end, next_period_start)
    Handles month-end dates safely (e.g., Jan 31 -> Feb 28 -> Mar 31).
    """
    if billing_cycle == "annually":
        delta = relativedelta(years=1)
    elif billing_cycle == "quarterly":
        delta = relativedelta(months=3)
    else:  # default monthly
        delta = relativedelta(months=1)

    next_start = start_date + delta
    period_end = next_start - relativedelta(days=1)
    return start_date, period_end, next_start


# ─── 2. Numbering Sequence ────────────────────────────────────────────────────

def generate_invoice_number() -> str:
    """Generate sequential invoice number: INV-YYYY-0001."""
    year = timezone.now().year
    prefix = f"INV-{year}-"
    last_inv = (
        Invoice.objects.filter(number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    if last_inv:
        try:
            last_seq = int(last_inv.split("-")[-1])
            next_seq = last_seq + 1
        except ValueError:
            next_seq = 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:04d}"


# ─── 3. Financial Calculation Pipeline ────────────────────────────────────────

def calculate_invoice_totals(subscription: Subscription, discount_code: str = None) -> dict:
    """
    Pure calculation pipeline for an invoice from a subscription's lines:
    1. Line Subtotal: qty * unit_price
    2. Product Discount: discount matching specific product
    3. Subscription Discount: discount applied across lines / total
    4. Tax: line_net * (tax_rate / 100)
    5. Line Total: line_net + tax_amount
    All rounded strictly to 2 decimal places.
    """
    lines_data = []
    subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    tax_total = Decimal("0.00")

    # Optional discount lookup
    discount_obj = None
    if discount_code:
        try:
            discount_obj = Discount.objects.get(code=discount_code, is_active=True)
            if not discount_obj.is_available:
                discount_obj = None
        except Discount.DoesNotExist:
            discount_obj = None

    sub_lines = list(subscription.lines.select_related("plan__product", "tax_rule").all())

    # First pass: calculate line subtotals & product-specific discounts
    for line in sub_lines:
        qty = line.quantity
        price = Decimal(str(line.unit_price))
        line_sub = round_curr(price * qty)
        subtotal += line_sub

        line_disc = Decimal("0.00")
        if discount_obj and discount_obj.scope == Discount.Scope.SPECIFIC_PRODUCT:
            if discount_obj.product_id == line.plan.product_id:
                if discount_obj.discount_type == Discount.DiscountType.PERCENT:
                    line_disc = round_curr(line_sub * (discount_obj.value / Decimal("100")))
                else:
                    line_disc = min(line_sub, round_curr(discount_obj.value))

        lines_data.append({
            "line_ref": line,
            "des   pricecription": f"{line.plan.product.name} - {line.plan.name}",
            "quantity": qty,
            "unit_price": price,
            "subtotal": line_sub,
            "discount_amount": line_disc,
            "tax_rate": Decimal(str(line.tax_rule.rate)) if line.tax_rule else Decimal("0.00"),
        })

    # Second pass: subscription-wide discount if applicable
    if discount_obj and discount_obj.scope in (Discount.Scope.ALL, Discount.Scope.SUBSCRIPTION):
        if discount_obj.discount_type == Discount.DiscountType.PERCENT:
            for l in lines_data:
                extra_disc = round_curr((l["subtotal"] - l["discount_amount"]) * (discount_obj.value / Decimal("100")))
                l["discount_amount"] += extra_disc
        else:
            # Fixed amount: distribute proportionally
            rem_disc = round_curr(discount_obj.value)
            for l in lines_data:
                applied = min(l["subtotal"] - l["discount_amount"], rem_disc)
                l["discount_amount"] += applied
                rem_disc -= applied
                if rem_disc <= Decimal("0.00"):
                    break

    # Third pass: compute tax and line total per line
    for l in lines_data:
        discount_total += l["discount_amount"]
        line_net = max(Decimal("0.00"), l["subtotal"] - l["discount_amount"])
        tax_amt = round_curr(line_net * (l["tax_rate"] / Decimal("100")))
        tax_total += tax_amt
        l["tax_amount"] = tax_amt
        l["line_total"] = line_net + tax_amt

    total = subtotal - discount_total + tax_total

    return {
        "subtotal": round_curr(subtotal),
        "discount_total": round_curr(discount_total),
        "tax_total": round_curr(tax_total),
        "total": round_curr(total),
        "lines": lines_data,
        "discount": discount_obj,
    }


# ─── 4. Idempotent Billing Engine ─────────────────────────────────────────────

def run_billing(target_date: date = None, dry_run: bool = False, actor=None) -> dict:
    """
    Executes the billing run for all active subscriptions due on or before target_date.
    - Row-level locking on subscriptions (select_for_update)
    - Checks for existing active invoice (unique_active_subscription_period constraint)
    - Atomic execution with savepoints
    - Dry-run mode for previewing billing results
    """
    if target_date is None:
        target_date = timezone.localdate()

    created_invoices = []
    skipped_count = 0
    total_amount = Decimal("0.00")

    with transaction.atomic():
        # Lock subscriptions to avoid race conditions with concurrent jobs
        due_subs = (
            Subscription.objects.select_for_update()
            .filter(
                status=Subscription.Status.ACTIVE,
                next_billing_date__lte=target_date,
            )
            .select_related("customer")
            .prefetch_related("lines__plan__product", "lines__tax_rule")
        )

        for sub in due_subs:
            period_start = sub.next_billing_date or target_date

            # Determine dominant cycle from lines (default monthly)
            first_line = sub.lines.first()
            cycle = first_line.plan.billing_cycle if first_line else "monthly"
            p_start, p_end, next_start = calculate_period(period_start, cycle)

            # Check if active invoice already exists for this period
            existing = Invoice.objects.filter(
                subscription=sub,
                period_start=p_start,
            ).exclude(status=Invoice.Status.CANCELLED).first()

            if existing:
                skipped_count += 1
                continue

            calc = calculate_invoice_totals(sub)
            if not calc["lines"]:
                skipped_count += 1
                continue

            inv_number = generate_invoice_number() if not dry_run else f"PREVIEW-{sub.id}"
            due_date = p_start + relativedelta(days=15)  # 15-day payment term

            if dry_run:
                created_invoices.append({
                    "subscription_id": sub.id,
                    "subscription_number": sub.number,
                    "customer": sub.customer.username,
                    "period_start": p_start,
                    "period_end": p_end,
                    "subtotal": calc["subtotal"],
                    "discount_total": calc["discount_total"],
                    "tax_total": calc["tax_total"],
                    "total": calc["total"],
                    "lines_count": len(calc["lines"]),
                })
                total_amount += calc["total"]
                continue

            # Real Run: Persist invoice
            invoice = Invoice.objects.create(
                number=inv_number,
                subscription=sub,
                period_start=p_start,
                period_end=p_end,
                due_date=due_date,
                status=Invoice.Status.DRAFT,
                subtotal=calc["subtotal"],
                discount_total=calc["discount_total"],
                tax_total=calc["tax_total"],
                total=calc["total"],
            )

            # Persist frozen lines
            for l in calc["lines"]:
                InvoiceLine.objects.create(
                    invoice=invoice,
                    description=l["description"],
                    quantity=l["quantity"],
                    unit_price=l["unit_price"],
                    discount_amount=l["discount_amount"],
                    tax_rate=l["tax_rate"],
                    tax_amount=l["tax_amount"],
                    line_total=l["line_total"],
                )

            # Log status change
            InvoiceStatusChange.objects.create(
                invoice=invoice,
                from_status="",
                to_status=Invoice.Status.DRAFT,
                changed_by=actor,
                note="Generated by billing run",
            )

            # Advance subscription billing date
            sub.next_billing_date = next_start
            sub.save(update_fields=["next_billing_date"])

            created_invoices.append({
                "uuid": str(invoice.uuid),
                "number": invoice.number,
                "subscription_number": sub.number,
                "customer": sub.customer.username,
                "period": f"{p_start} to {p_end}",
                "total": invoice.total,
            })
            total_amount += invoice.total

        if dry_run:
            # Force rollback for dry-run
            transaction.set_rollback(True)

    return {
        "dry_run": dry_run,
        "target_date": str(target_date),
        "created_count": len(created_invoices),
        "skipped_count": skipped_count,
        "total_amount": round_curr(total_amount),
        "invoices": created_invoices,
    }


# ─── 5. Payment Recording Service ─────────────────────────────────────────────

def record_payment(
    invoice_uuid: str,
    amount: Decimal,
    payment_date: date,
    method: str = "bank_transfer",
    reference: str = "",
    note: str = "",
    recorded_by=None,
) -> Payment:
    """
    Records a payment against an invoice:
    - Locks invoice row with select_for_update()
    - Rejects non-positive payments and overpayments
    - Automatically updates invoice status to PAID if balance reaches 0
    - Records audit history in InvoiceStatusChange
    """
    amount = round_curr(Decimal(str(amount)))
    if amount <= Decimal("0.00"):
        raise ValidationError("Payment amount must be greater than zero.")

    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(uuid=invoice_uuid)

        if invoice.status == Invoice.Status.CANCELLED:
            raise ValidationError("Cannot record payment on a cancelled invoice.")

        balance = invoice.balance_due
        if amount > balance:
            raise ValidationError(
                f"Payment amount (₹{amount}) exceeds remaining balance (₹{balance})."
            )

        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            payment_date=payment_date,
            method=method,
            reference=reference,
            note=note,
            recorded_by=recorded_by,
        )

        # Check new balance
        new_balance = invoice.balance_due
        old_status = invoice.status
        if new_balance == Decimal("0.00"):
            invoice.status = Invoice.Status.PAID
            invoice.save(update_fields=["status"])
            InvoiceStatusChange.objects.create(
                invoice=invoice,
                from_status=old_status,
                to_status=Invoice.Status.PAID,
                changed_by=recorded_by,
                note=f"Paid in full via payment #{payment.id}",
            )

    return payment


# ─── 6. Invoice Status Actions ────────────────────────────────────────────────

def confirm_invoice(invoice: Invoice, actor=None) -> Invoice:
    if invoice.status != Invoice.Status.DRAFT:
        raise ValidationError("Only draft invoices can be confirmed.")
    old = invoice.status
    invoice.status = Invoice.Status.CONFIRMED
    invoice.save(update_fields=["status"])
    InvoiceStatusChange.objects.create(
        invoice=invoice,
        from_status=old,
        to_status=Invoice.Status.CONFIRMED,
        changed_by=actor,
        note="Confirmed by staff",
    )
    return invoice


def send_invoice(invoice: Invoice, actor=None) -> Invoice:
    if invoice.status not in (Invoice.Status.CONFIRMED, Invoice.Status.DRAFT):
        raise ValidationError("Invoice must be draft or confirmed to send.")
    old = invoice.status
    invoice.status = Invoice.Status.SENT
    invoice.save(update_fields=["status"])
    InvoiceStatusChange.objects.create(
        invoice=invoice,
        from_status=old,
        to_status=Invoice.Status.SENT,
        changed_by=actor,
        note="Dispatched invoice notification",
    )
    return invoice


def cancel_invoice(invoice: Invoice, reason: str = "", actor=None) -> Invoice:
    if invoice.status == Invoice.Status.PAID:
        raise ValidationError("Paid invoices cannot be cancelled.")
    old = invoice.status
    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status"])
    InvoiceStatusChange.objects.create(
        invoice=invoice,
        from_status=old,
        to_status=Invoice.Status.CANCELLED,
        changed_by=actor,
        note=f"Cancelled: {reason}" if reason else "Cancelled by staff",
    )
    return invoice


def send_reminder(invoice: Invoice, actor=None) -> dict:
    today = timezone.localdate()
    invoice.last_reminded_date = today
    invoice.reminder_count = F("reminder_count") + 1
    invoice.save(update_fields=["last_reminded_date", "reminder_count"])
    invoice.refresh_from_db()
    return {
        "invoice": invoice.number,
        "last_reminded_date": str(invoice.last_reminded_date),
        "reminder_count": invoice.reminder_count,
    }


# ─── 7. CSV Export Helpers ────────────────────────────────────────────────────

def export_invoices_csv(queryset) -> str:
    """Generate CSV string of given invoices queryset."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice Number",
        "Customer",
        "Subscription",
        "Period Start",
        "Period End",
        "Status",
        "Subtotal",
        "Discount",
        "Tax",
        "Total",
        "Total Paid",
        "Balance Due",
        "Due Date",
    ])
    for inv in queryset.select_related("subscription__customer"):
        writer.writerow([
            inv.number,
            inv.subscription.customer.username,
            inv.subscription.number,
            inv.period_start,
            inv.period_end,
            inv.status,
            inv.subtotal,
            inv.discount_total,
            inv.tax_total,
            inv.total,
            inv.total_paid,
            inv.balance_due,
            inv.due_date,
        ])
    return output.getvalue()


def export_payments_csv(queryset) -> str:
    """Generate CSV string of given payments queryset."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Payment ID",
        "Invoice Number",
        "Amount",
        "Date",
        "Method",
        "Reference",
        "Recorded By",
    ])
    for p in queryset.select_related("invoice", "recorded_by"):
        writer.writerow([
            p.id,
            p.invoice.number,
            p.amount,
            p.payment_date,
            p.method,
            p.reference,
            p.recorded_by.username if p.recorded_by else "",
        ])
    return output.getvalue()

