from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .forms import PlanForm, ProductForm, TaxRuleForm
from .models import Plan, Product, ProductVariant, TaxRule, validate_plan_available


def plan_data(**overrides):
    data = {"name": "Monthly", "price": "1000.00", "billing_period": "monthly",
            "min_quantity": "1", "is_active": "on", "closable": "on", "pausable": "on", "renewable": "on"}
    data.update(overrides)
    return data


class ValidationTests(TestCase):
    def test_tax_rate_between_0_and_100(self):
        form = TaxRuleForm({"name": "Bad", "rate": "120", "is_active": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("Tax rate must be between 0 and 100.", form.errors["rate"])

    def test_product_prices_not_negative(self):
        form = ProductForm({"name": "X", "product_type": "service", "sales_price": "-1", "cost_price": "0"})
        self.assertFalse(form.is_valid())
        self.assertIn("Enter an amount of 0 or more.", form.errors["sales_price"])

    def test_plan_price_must_be_positive(self):
        form = PlanForm(plan_data(price="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("Price must be more than 0.", form.errors["price"])

    def test_plan_min_quantity_at_least_1(self):
        form = PlanForm(plan_data(min_quantity="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("Minimum quantity must be at least 1.", form.errors["min_quantity"])

    def test_plan_end_date_after_start_date(self):
        form = PlanForm(plan_data(start_date="2026-12-01", end_date="2026-12-01"))
        self.assertFalse(form.is_valid())
        self.assertIn("End date must be after start date.", form.errors["end_date"])

    def test_valid_plan(self):
        form = PlanForm(plan_data(start_date="2026-01-01", end_date="2026-12-31"))
        self.assertTrue(form.is_valid(), form.errors)


class PlanAvailabilityTests(TestCase):
    def test_only_plans_inside_their_dates_are_available(self):
        today = timezone.localdate()
        open_plan = Plan.objects.create(name="Open", price=10)
        current = Plan.objects.create(name="Current", price=10,
                                      start_date=today - timedelta(days=1), end_date=today)
        future = Plan.objects.create(name="Future", price=10, start_date=today + timedelta(days=1))
        expired = Plan.objects.create(name="Expired", price=10,
                                      start_date=today - timedelta(days=10), end_date=today - timedelta(days=1))
        inactive = Plan.objects.create(name="Inactive", price=10, is_active=False)

        self.assertEqual(set(Plan.objects.available()), {open_plan, current})
        for plan in (future, expired, inactive):
            with self.subTest(plan=plan.name):
                self.assertFalse(plan.is_available())
                with self.assertRaisesMessage(ValidationError, "This plan isn't available on that date."):
                    validate_plan_available(plan)
        validate_plan_available(current)  # no error


class ProductPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin@example.com", "Test-pass-123!", name="Admin", role="admin")
        cls.staff = User.objects.create_user("staff@example.com", "Test-pass-123!", name="Staff", role="staff")
        cls.tax = TaxRule.objects.create(name="GST 18%", rate="18.00")

    def product_post(self, variants):
        data = {
            "name": "CRM Suite", "product_type": "service", "sales_price": "1000.00",
            "cost_price": "400.00", "tax_rule": self.tax.pk, "notes": "", "is_active": "on",
            "variants-TOTAL_FORMS": str(len(variants)), "variants-INITIAL_FORMS": "0",
            "variants-MIN_NUM_FORMS": "0", "variants-MAX_NUM_FORMS": "1000",
        }
        for i, (attribute, value, extra) in enumerate(variants):
            data.update({f"variants-{i}-attribute": attribute, f"variants-{i}-value": value,
                         f"variants-{i}-extra_price": extra})
        return data

    def test_admin_creates_product_with_variants(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("products:product_create"),
                                    self.product_post([("Brand", "Odoo", "560"), ("", "", "0.00")]))  # untouched extra row
        product = Product.objects.get()
        self.assertRedirects(response, reverse("products:product_detail", args=[product.pk]))
        self.assertEqual(list(product.variants.values_list("attribute", "value")), [("Brand", "Odoo")])

    def test_duplicate_variant_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("products:product_create"),
                                    self.product_post([("Brand", "Odoo", "560"), ("brand", "odoo", "0")]))
        self.assertContains(response, "This variant already exists.")
        self.assertFalse(Product.objects.exists())

    def test_staff_can_view_but_not_edit(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("products:list")).status_code, 200)
        response = self.client.post(reverse("products:product_create"), self.product_post([]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Product.objects.exists())

    def test_tax_in_use_cannot_be_deleted(self):
        Product.objects.create(name="Uses tax", tax_rule=self.tax)
        self.client.force_login(self.admin)
        self.client.post(reverse("products:tax_delete", args=[self.tax.pk]))
        self.assertTrue(TaxRule.objects.filter(pk=self.tax.pk).exists())

    def test_admin_creates_plan(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("products:plan_create"), plan_data(name="Yearly", billing_period="yearly"))
        self.assertTrue(Plan.objects.filter(name="Yearly", billing_period="yearly").exists())

    def test_variant_alias_still_works(self):
        from .models import Variant
        self.assertIs(Variant, ProductVariant)
