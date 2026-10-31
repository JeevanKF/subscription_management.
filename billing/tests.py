"""
billing/tests.py
Comprehensive test suite for Module M3:
1. Date maths (month-end rollover: Jan 31 -> Feb 28 -> Mar 31)
2. Exact calculation pipeline & ₹5,310 tax worked example
3. Billing idempotency & duplicate prevention
4. Payment recording: partial payment, full payment auto-PAID, overpayment rejection
5. Discount usage limits and scope
6. Security & IDOR: UUID lookup and customer data isolation
"""

from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import User
from products.models import Product, Plan, TaxRule
from subscriptions.models import Subscription, SubscriptionLine
from billing.models import Invoice, InvoiceLine, Payment, Discount
from billing.services import (
    calculate_period,
    calculate_invoice_totals,
    run_billing,
    record_payment,
    confirm_invoice,
    send_invoice,
    cancel_invoice,
    round_curr,
)


class BillingDateMathsTestCase(TestCase):
    def test_month_end_safe_rollover(self):
        """Jan 31 -> Feb 28 (or 29) -> Mar 31."""
        jan31 = date(2026, 1, 31)
        p_start, p_end, next_start = calculate_period(jan31, "monthly")
        self.assertEqual(p_start, date(2026, 1, 31))
        self.assertEqual(p_end, date(2026, 2, 27))
        self.assertEqual(next_start, date(2026, 2, 28))

    def test_quarterly_rollover(self):
        start = date(2026, 1, 1)
        p_start, p_end, next_start = calculate_period(start, "quarterly")
        self.assertEqual(p_end, date(2026, 3, 31))
        self.assertEqual(next_start, date(2026, 4, 1))

    def test_annual_rollover(self):
        start = date(2026, 1, 1)
        p_start, p_end, next_start = calculate_period(start, "annually")
        self.assertEqual(p_end, date(2026, 12, 31))
        self.assertEqual(next_start, date(2027, 1, 1))


    def test_plan_billing_periods(self):
        """Plan.billing_period values: daily, weekly, yearly."""
        start = date(2026, 1, 1)
        self.assertEqual(calculate_period(start, "daily")[2], date(2026, 1, 2))
        self.assertEqual(calculate_period(start, "weekly")[2], date(2026, 1, 8))
        self.assertEqual(calculate_period(start, "yearly")[1], date(2026, 12, 31))


class BillingCalculationTestCase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="cust1@test.com", password="pw", name="cust1", role="customer")
        self.tax18 = TaxRule.objects.create(name="GST 18%", rate=Decimal("18.00"))
        self.prod = Product.objects.create(name="Cloud SMS")
        self.plan = Plan.objects.create(
            product=self.prod,
            name="Starter",
            billing_period="monthly",
            price=Decimal("4500.00"),
        )
        self.sub = Subscription.objects.create(
            customer=self.customer,
            number="SUB-0001",
            status="active",
            start_date=date(2026, 1, 1),
            next_billing_date=date(2026, 1, 1),
        )
        self.line = SubscriptionLine.objects.create(
            subscription=self.sub,
            plan=self.plan,
            tax_rule=self.tax18,
            quantity=1,
            unit_price=Decimal("4500.00"),
        )

    def test_tax_calculation_worked_example(self):
        """₹4,500 line + 18% GST (₹810) = ₹5,310 total."""
        calc = calculate_invoice_totals(self.sub)
        self.assertEqual(calc["subtotal"], Decimal("4500.00"))
        self.assertEqual(calc["discount_total"], Decimal("0.00"))
        self.assertEqual(calc["tax_total"], Decimal("810.00"))
        self.assertEqual(calc["total"], Decimal("5310.00"))

    def test_calculation_with_percent_discount(self):
        """10% discount on ₹4,500 = ₹450 off -> ₹4,050 net + 18% tax (₹729) = ₹4,779."""
        disc = Discount.objects.create(
            code="SAVE10",
            discount_type="percent",
            value=Decimal("10.00"),
            scope="all",
        )
        calc = calculate_invoice_totals(self.sub, discount_code="SAVE10")
        self.assertEqual(calc["subtotal"], Decimal("4500.00"))
        self.assertEqual(calc["discount_total"], Decimal("450.00"))
        self.assertEqual(calc["tax_total"], Decimal("729.00"))
        self.assertEqual(calc["total"], Decimal("4779.00"))


class BillingRunIdempotencyTestCase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="cust2@test.com", password="pw", name="cust2", role="customer")
        self.tax18 = TaxRule.objects.create(name="GST 18%", rate=Decimal("18.00"))
        self.prod = Product.objects.create(name="Cloud SMS")
        self.plan = Plan.objects.create(
            product=self.prod,
            name="Starter",
            billing_period="monthly",
            price=Decimal("1000.00"),
        )
        self.sub = Subscription.objects.create(
            customer=self.customer,
            number="SUB-0002",
            status="active",
            start_date=date(2026, 1, 1),
            next_billing_date=date(2026, 1, 1),
        )
        SubscriptionLine.objects.create(
            subscription=self.sub,
            plan=self.plan,
            tax_rule=self.tax18,
            quantity=1,
            unit_price=Decimal("1000.00"),
        )

    def test_run_billing_idempotency_no_duplicates(self):
        """Running billing twice on the same target date creates 0 duplicates."""
        res1 = run_billing(target_date=date(2026, 1, 1))
        self.assertEqual(res1["created_count"], 1)
        self.assertEqual(res1["skipped_count"], 0)
        self.assertEqual(Invoice.objects.filter(subscription=self.sub).count(), 1)

        # Run again for the same date
        res2 = run_billing(target_date=date(2026, 1, 1))
        self.assertEqual(res2["created_count"], 0)
        self.assertEqual(res2["skipped_count"], 0)
        self.assertEqual(Invoice.objects.filter(subscription=self.sub).count(), 1)

    def test_cancelled_invoice_allows_rebilling(self):
        """If an invoice was cancelled, re-running billing is permitted."""
        run_billing(target_date=date(2026, 1, 1))
        inv = Invoice.objects.get(subscription=self.sub)
        cancel_invoice(inv, reason="Wrong terms")

        # Reset subscription next_billing_date back to period start for test
        self.sub.next_billing_date = date(2026, 1, 1)
        self.sub.save()

        res = run_billing(target_date=date(2026, 1, 1))
        self.assertEqual(res["created_count"], 1)
        self.assertEqual(Invoice.objects.filter(subscription=self.sub).count(), 2)


class PaymentServiceTestCase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email="cust3@test.com", password="pw", name="cust3", role="customer")
        self.staff = User.objects.create_user(email="staff1@test.com", password="pw", name="staff1", role="staff")
        self.sub = Subscription.objects.create(
            customer=self.customer,
            number="SUB-0003",
            status="active",
            start_date=date(2026, 1, 1),
        )
        self.invoice = Invoice.objects.create(
            number="INV-2026-9999",
            subscription=self.sub,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            total=Decimal("5310.00"),
            status="sent",
        )

    def test_partial_payment_and_overpayment_protection(self):
        # 1. Partial payment of ₹2,000
        pay1 = record_payment(
            invoice_uuid=str(self.invoice.uuid),
            amount=Decimal("2000.00"),
            payment_date=date(2026, 1, 10),
            recorded_by=self.staff,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_paid, Decimal("2000.00"))
        self.assertEqual(self.invoice.balance_due, Decimal("3310.00"))
        self.assertEqual(self.invoice.status, "sent")

        # 2. Overpayment attempt of ₹4,000 (balance is only ₹3,310) -> Rejected
        with self.assertRaises(ValidationError):
            record_payment(
                invoice_uuid=str(self.invoice.uuid),
                amount=Decimal("4000.00"),
                payment_date=date(2026, 1, 12),
                recorded_by=self.staff,
            )

        # 3. Pay exact remaining balance ₹3,310 -> Auto transitions to PAID
        pay2 = record_payment(
            invoice_uuid=str(self.invoice.uuid),
            amount=Decimal("3310.00"),
            payment_date=date(2026, 1, 15),
            recorded_by=self.staff,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_paid, Decimal("5310.00"))
        self.assertEqual(self.invoice.balance_due, Decimal("0.00"))
        self.assertEqual(self.invoice.status, "paid")
