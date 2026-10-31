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
from subscriptions.services import generate_subscription_number

User = get_user_model()

PERIOD_DELTA = {"weekly": relativedelta(weeks=1), "monthly": relativedelta(months=1),
                "yearly": relativedelta(years=1)}
# Price multiplier against the monthly base price
PERIOD_PRICE_FACTOR = {"weekly": Decimal("0.25"), "monthly": Decimal(1), "yearly": Decimal(10)}

PRODUCT_CATALOGUE = [
    ("Cloud Backup", ["Standard", "Pro"]),
    ("Helpdesk Suite", ["Basic", "Enterprise"]),
    ("Analytics Platform", ["Lite", "Premium"]),
    ("CRM Toolkit", ["Starter", "Growth"]),
    ("Security Shield", ["Essential", "Advanced"]),
]

PLAN_CYCLES = [Plan.BillingPeriod.WEEKLY, Plan.BillingPeriod.MONTHLY, Plan.BillingPeriod.YEARLY]

SUB_STATUS_WEIGHTS = [
    (Subscription.Status.ACTIVE, 60),
    (Subscription.Status.PAUSED, 15),
    (Subscription.Status.CLOSED, 15),
    (Subscription.Status.DRAFT, 6),
    (Subscription.Status.QUOTATION, 4),
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
        User.objects.filter(role="customer", email__startswith="customer").delete()
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
                defaults={"notes": f"{product_name} subscription product.",
                          "sales_price": Decimal(random.choice([299, 499, 999]))},
            )
            for variant_name in variant_names:
                Variant.objects.get_or_create(
                    product=product, attribute="Edition", value=variant_name,
                    defaults={"extra_price": Decimal(random.choice([0, 199, 499]))},
                )
            for cycle in PLAN_CYCLES:
                base_price = Decimal(random.choice([299, 499, 999, 1999]))
                price = base_price * PERIOD_PRICE_FACTOR[cycle]
                plan, _ = Plan.objects.get_or_create(
                    product=product, name=f"{product_name} ({cycle.title()})",
                    defaults={"billing_period": cycle, "price": price},
                )
                plans.append(plan)
        self.stdout.write(f"Products: {len(PRODUCT_CATALOGUE)}, Plans: {len(plans)}")
        return plans

    def _seed_customers(self, count):
        existing = list(User.objects.filter(role="customer", email__startswith="customer"))
        if len(existing) >= count:
            return existing[:count]

        to_create = []
        for i in range(len(existing), count):
            user = User(
                email=f"customer{i + 1}@example.test",
                name=f"Customer {i + 1}",
                role=User.Role.CUSTOMER,
            )
            user.set_password("password123")
            to_create.append(user)

        User.objects.bulk_create(to_create, batch_size=500)
        self.stdout.write(f"Customers created: {len(to_create)}")
        return list(User.objects.filter(role="customer", email__startswith="customer")[:count])

    @transaction.atomic
    def _seed_subscriptions(self, count, customers, plans, tax_rules):
        today = date.today()
        # Continue the SUB-0001 sequence used by subscriptions.services
        first_seq = int(generate_subscription_number().removeprefix("SUB-"))

        subscriptions, sub_plans = [], []
        for i in range(count):
            plan = random.choice(plans)
            status = _weighted_choice(SUB_STATUS_WEIGHTS)
            start_date = today - timedelta(days=random.randint(0, 540))
            billing = status in (Subscription.Status.ACTIVE, Subscription.Status.PAUSED)
            next_billing_date = start_date + PERIOD_DELTA[plan.billing_period] if billing else None
            quotation_expiry = (today + timedelta(days=random.randint(1, 30))
                                if status == Subscription.Status.QUOTATION else None)

            subscriptions.append(Subscription(
                customer=random.choice(customers),
                plan=plan,
                number=f"SUB-{first_seq + i:04d}",
                status=status,
                start_date=start_date,
                quotation_expiry=quotation_expiry,
                next_billing_date=next_billing_date,
            ))
            sub_plans.append(plan)

        Subscription.objects.bulk_create(subscriptions, batch_size=500)
        created_subs = list(Subscription.objects.order_by("-id")[:count])
        created_subs.reverse()

        variants_by_product = {}
        for variant in Variant.objects.all():
            variants_by_product.setdefault(variant.product_id, []).append(variant)

        lines, invoices_plan = [], []
        for sub, plan in zip(created_subs, sub_plans):
            quantity = random.randint(plan.min_quantity, max(3, plan.min_quantity))
            variant_choices = variants_by_product.get(plan.product_id) or [None]
            lines.append(SubscriptionLine(
                subscription=sub,
                product=plan.product,
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
            no_invoices = (Subscription.Status.DRAFT, Subscription.Status.QUOTATION)
            history_len = 0 if sub.status in no_invoices else random.randint(1, 4)
            period = PERIOD_DELTA[plan.billing_period]

            for n in range(history_len):
                counter += 1
                period_start = sub.start_date + period * n
                period_end = period_start + period - timedelta(days=1)
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
