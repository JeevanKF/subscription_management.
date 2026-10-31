"""
dashboard/management/commands/seed_data.py

Seeds demo data end to end: tax rules, products/variants/plans,
customers, subscriptions, invoices and payments. Used both for
local development and for the 5,000-subscription load/perf check.

Usage:
    python manage.py seed_data                      # small demo set
    python manage.py seed_data --subscriptions 5000  # load test size
    python manage.py seed_data --flush               # wipe seeded data first
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Discount, Invoice, InvoiceLine, Payment
from products.models import Plan, Product, TaxRule, Variant
from subscriptions.models import Subscription, SubscriptionLine

User = get_user_model()

CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "annually": 12}

PRODUCT_CATALOGUE = [
    ("Cloud Backup", ["Standard", "Pro"]),
    ("Helpdesk Suite", ["Basic", "Enterprise"]),
    ("Analytics Platform", ["Lite", "Premium"]),
    ("CRM Toolkit", ["Starter", "Growth"]),
    ("Security Shield", ["Essential", "Advanced"]),
]

PLAN_CYCLES = [Plan.BillingCycle.MONTHLY, Plan.BillingCycle.QUARTERLY, Plan.BillingCycle.ANNUALLY]

SUB_STATUS_WEIGHTS = [
    (Subscription.Status.ACTIVE, 60),
    (Subscription.Status.PAUSED, 15),
    (Subscription.Status.CLOSED, 15),
    (Subscription.Status.DRAFT, 10),
]

INVOICE_STATUS_WEIGHTS = [
    (Invoice.Status.PAID, 55),
    (Invoice.Status.OVERDUE, 15),
    (Invoice.Status.SENT, 15),
    (Invoice.Status.CONFIRMED, 10),
    (Invoice.Status.CANCELLED, 5),
]


def _weighted_choice(weights):
    values, weights_ = zip(*weights)
    return random.choices(values, weights=weights_, k=1)[0]


class Command(BaseCommand):
    help = "Seed tax rules, products, customers, subscriptions, invoices and payments."

    def add_arguments(self, parser):
        parser.add_argument("--customers", type=int, default=50)
        parser.add_argument("--subscriptions", type=int, default=200)
        parser.add_argument("--flush", action="store_true", help="Delete previously seeded data first.")

    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        tax_rules = self._seed_tax_rules()
        plans = self._seed_catalogue()
        customers = self._seed_customers(options["customers"])
        self._seed_subscriptions(options["subscriptions"], customers, plans, tax_rules)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(customers)} customers and {options['subscriptions']} subscriptions."
        ))

    def _flush(self):
        self.stdout.write("Flushing previously seeded data...")
        Payment.objects.all().delete()
        InvoiceLine.objects.all().delete()
        Invoice.objects.all().delete()
        SubscriptionLine.objects.all().delete()
        Subscription.objects.all().delete()
        User.objects.filter(role="customer", username__startswith="customer").delete()
        Variant.objects.all().delete()
        Plan.objects.all().delete()
        Product.objects.all().delete()
        TaxRule.objects.all().delete()
        Discount.objects.all().delete()

    def _seed_tax_rules(self):
        rules = []
        for name, rate in [("GST 18%", Decimal("18.00")), ("GST 5%", Decimal("5.00")), ("No Tax", Decimal("0.00"))]:
            rule, _ = TaxRule.objects.get_or_create(name=name, defaults={"rate": rate})
            rules.append(rule)
        self.stdout.write(f"Tax rules: {len(rules)}")
        return rules

    def _seed_catalogue(self):
        plans = []
        for product_name, variant_names in PRODUCT_CATALOGUE:
            product, _ = Product.objects.get_or_create(
                name=product_name,
                defaults={"description": f"{product_name} subscription product."},
            )
            for variant_name in variant_names:
                Variant.objects.get_or_create(
                    product=product, name=variant_name,
                    defaults={"extra_price": Decimal(random.choice([0, 199, 499]))},
                )
            for cycle in PLAN_CYCLES:
                base_price = Decimal(random.choice([299, 499, 999, 1999]))
                price = base_price * CYCLE_MONTHS[cycle]
                plan, _ = Plan.objects.get_or_create(
                    product=product, name=f"{product_name} ({cycle.title()})",
                    defaults={"billing_cycle": cycle, "price": price},
                )
                plans.append(plan)
        self.stdout.write(f"Products: {len(PRODUCT_CATALOGUE)}, Plans: {len(plans)}")
        return plans

    def _seed_customers(self, count):
        existing = list(User.objects.filter(role="customer", username__startswith="customer"))
        if len(existing) >= count:
            return existing[:count]

        to_create = []
        for i in range(len(existing), count):
            user = User(
                username=f"customer{i + 1}",
                email=f"customer{i + 1}@example.test",
                first_name="Customer",
                last_name=str(i + 1),
                role=User.Role.CUSTOMER,
            )
            user.set_password("password123")
            to_create.append(user)

        User.objects.bulk_create(to_create, batch_size=500)
        self.stdout.write(f"Customers created: {len(to_create)}")
        return list(User.objects.filter(role="customer", username__startswith="customer")[:count])

    @transaction.atomic
    def _seed_subscriptions(self, count, customers, plans, tax_rules):
        today = date.today()
        existing_count = Subscription.objects.count()

        subscriptions = []
        for i in range(count):
            number = f"SUB-{existing_count + i + 1:06d}"
            status = _weighted_choice(SUB_STATUS_WEIGHTS)
            start_date = today - timedelta(days=random.randint(0, 540))
            next_billing_date = None if status in (Subscription.Status.DRAFT, Subscription.Status.CLOSED) \
                else start_date + relativedelta(months=1)

            subscriptions.append(Subscription(
                customer=random.choice(customers),
                number=number,
                status=status,
                start_date=start_date,
                next_billing_date=next_billing_date,
            ))

        Subscription.objects.bulk_create(subscriptions, batch_size=500)
        created_subs = list(Subscription.objects.order_by("-id")[:count])
        created_subs.reverse()

        variants_by_product = {}
        for variant in Variant.objects.all():
            variants_by_product.setdefault(variant.product_id, []).append(variant)

        lines, invoices_plan = [], []
        for sub in created_subs:
            plan = random.choice(plans)
            quantity = random.randint(1, 3)
            variant_choices = variants_by_product.get(plan.product_id) or [None]
            lines.append(SubscriptionLine(
                subscription=sub,
                plan=plan,
                variant=random.choice(variant_choices),
                tax_rule=random.choice(tax_rules),
                quantity=quantity,
                unit_price=plan.price,
            ))
            invoices_plan.append((sub, plan, quantity))

        SubscriptionLine.objects.bulk_create(lines, batch_size=500)
        self.stdout.write(f"Subscriptions created: {len(created_subs)}")

        self._seed_invoices(invoices_plan)

    def _seed_invoices(self, invoices_plan):
        today = date.today()
        existing_count = Invoice.objects.count()
        counter = existing_count

        invoices, invoice_meta = [], []
        for sub, plan, quantity in invoices_plan:
            history_len = random.randint(1, 4) if sub.status != Subscription.Status.DRAFT else 0
            cycle_months = CYCLE_MONTHS[plan.billing_cycle]

            for n in range(history_len):
                counter += 1
                period_start = sub.start_date + relativedelta(months=cycle_months * n)
                period_end = period_start + relativedelta(months=cycle_months) - timedelta(days=1)
                status = _weighted_choice(INVOICE_STATUS_WEIGHTS)
                subtotal = plan.price * quantity
                tax_total = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
                total = subtotal + tax_total

                invoices.append(Invoice(
                    subscription=sub,
                    number=f"INV-{counter:06d}",
                    period_start=period_start,
                    period_end=period_end,
                    status=status,
                    subtotal=subtotal,
                    tax_total=tax_total,
                    total=total,
                    due_date=period_end + timedelta(days=15),
                ))
                invoice_meta.append((plan, quantity, status, total))

        Invoice.objects.bulk_create(invoices, batch_size=500)
        created_invoices = list(Invoice.objects.order_by("-id")[:len(invoices)])
        created_invoices.reverse()

        invoice_lines, payments = [], []
        for invoice, (plan, quantity, status, total) in zip(created_invoices, invoice_meta):
            invoice_lines.append(InvoiceLine(
                invoice=invoice,
                description=plan.name,
                quantity=quantity,
                unit_price=plan.price,
                tax_rate=Decimal("18.00"),
                line_total=invoice.subtotal,
            ))
            if status == Invoice.Status.PAID:
                payments.append(Payment(
                    invoice=invoice,
                    amount=total,
                    payment_date=invoice.due_date - timedelta(days=random.randint(0, 10)),
                    note="Seed payment",
                ))

        InvoiceLine.objects.bulk_create(invoice_lines, batch_size=500)
        Payment.objects.bulk_create(payments, batch_size=500)
        self.stdout.write(f"Invoices created: {len(created_invoices)}, payments: {len(payments)}")
