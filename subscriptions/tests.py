"""
subscriptions/tests.py
Business-rule tests for the subscription lifecycle (services.py) and the API
(permissions, customer scoping, filters, templates).

    python manage.py test subscriptions
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from products.models import Plan, Product, ProductVariant, TaxRule

from . import services
from .models import QuotationTemplate, Subscription, SubscriptionStatusChange, TemplateLine

Status = Subscription.Status
TODAY = timezone.localdate()


class SubscriptionTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email="admin@test.com", name="Admin", role="admin")
        cls.staff = User.objects.create_user(email="staff@test.com", name="Staff", role="staff")
        cls.customer = User.objects.create_user(email="asha@test.com", name="Asha", role="customer")
        cls.other = User.objects.create_user(email="ravi@test.com", name="Ravi", role="customer")

        cls.gst = TaxRule.objects.create(name="GST 18%", rate=Decimal("18.00"))
        cls.product = Product.objects.create(name="CRM Suite", sales_price=Decimal("1000.00"), tax_rule=cls.gst)
        cls.addon = Product.objects.create(name="Extra Storage", sales_price=Decimal("200.00"))
        cls.variant = ProductVariant.objects.create(product=cls.product, attribute="Brand", value="Odoo",
                                                    extra_price=Decimal("560.00"))
        cls.plan = Plan.objects.create(name="CRM Monthly", product=cls.product, price=Decimal("800.00"),
                                       min_quantity=2)
        cls.locked_plan = Plan.objects.create(name="Locked Yearly", product=cls.product, price=Decimal("9000"),
                                              billing_period="yearly", pausable=False, renewable=False,
                                              closable=False)
        cls.auto_plan = Plan.objects.create(name="Auto-close", product=cls.product, price=Decimal("500"),
                                            auto_close=True)

    def make(self, plan=None, customer=None, quantity=2, start_date=TODAY, expiry_date=None, **kwargs):
        return services.create_subscription(
            customer=customer or self.customer, plan=plan or self.plan, start_date=start_date,
            expiry_date=expiry_date, actor=self.staff,
            lines=[{"product": self.product, "quantity": quantity}], **kwargs,
        )

    def make_active(self, **kwargs):
        sub = self.make(**kwargs)
        services.send_quote(sub, actor=self.staff)
        services.confirm_subscription(sub, actor=self.staff)
        services.activate_subscription(sub, actor=self.staff)
        return sub

    def history(self, sub):
        return list(sub.status_changes.values_list("from_status", "to_status"))


# ─── Creation and numbering ───────────────────────────────────────────────────

class CreateSubscriptionTests(SubscriptionTestBase):
    def test_creates_draft_with_lines_and_history(self):
        sub = self.make()
        self.assertEqual(sub.status, Status.DRAFT)
        self.assertEqual(sub.number, "SUB-0001")
        self.assertEqual(sub.created_by, self.staff)
        line = sub.lines.get()
        self.assertEqual(line.plan, self.plan)            # mirrored for billing
        self.assertEqual(line.unit_price, Decimal("800.00"))   # plan's own product → plan price
        self.assertEqual(line.tax_rule, self.gst)         # product default tax
        self.assertEqual(line.amount, Decimal("1888.00"))  # 1600 + 18%
        self.assertEqual(self.history(sub), [("", Status.DRAFT)])

    def test_numbers_are_sequential_and_unique(self):
        numbers = [self.make().number for _ in range(3)]
        self.assertEqual(numbers, ["SUB-0001", "SUB-0002", "SUB-0003"])

    def test_numbering_continues_after_highest_existing(self):
        sub = self.make()
        Subscription.objects.filter(pk=sub.pk).update(number="SUB-0041")
        self.assertEqual(self.make().number, "SUB-0042")

    def test_variant_adds_extra_price_and_other_products_use_sales_price(self):
        sub = services.create_subscription(
            customer=self.customer, plan=self.plan, start_date=TODAY, actor=self.staff,
            lines=[{"product": self.product, "variant": self.variant, "quantity": 2},
                   {"product": self.addon, "quantity": 3}],
        )
        prices = list(sub.lines.values_list("unit_price", flat=True))
        self.assertEqual(prices, [Decimal("1360.00"), Decimal("200.00")])

    def test_quantity_below_plan_minimum_is_rejected(self):
        with self.assertRaisesMessage(services.SubscriptionError, "at least 2"):
            self.make(quantity=1)
        self.assertFalse(Subscription.objects.exists())

    def test_requires_a_customer(self):
        with self.assertRaises(services.SubscriptionError):
            self.make(customer=self.staff)

    def test_requires_lines(self):
        with self.assertRaises(services.SubscriptionError):
            services.create_subscription(customer=self.customer, plan=self.plan, start_date=TODAY, lines=[])

    def test_rejects_plan_not_available_on_start_date(self):
        self.plan.end_date = TODAY - timedelta(days=1)
        self.plan.start_date = TODAY - timedelta(days=30)
        self.plan.save()
        with self.assertRaisesMessage(services.SubscriptionError, "isn't available"):
            self.make()

    def test_rejects_variant_of_another_product(self):
        with self.assertRaises(services.SubscriptionError):
            services.create_subscription(
                customer=self.customer, plan=self.plan, start_date=TODAY,
                lines=[{"product": self.addon, "variant": self.variant, "quantity": 2}],
            )

    def test_rejects_expiry_before_start(self):
        with self.assertRaises(services.SubscriptionError):
            self.make(expiry_date=TODAY - timedelta(days=1))

    def test_update_draft_replaces_lines_but_not_after_quote(self):
        sub = self.make()
        services.update_draft(sub, lines=[{"product": self.addon, "quantity": 5}])
        self.assertEqual(list(sub.lines.values_list("product__name", "quantity")), [("Extra Storage", 5)])
        services.send_quote(sub, actor=self.staff)
        with self.assertRaises(services.SubscriptionError):
            services.update_draft(sub, notes="too late")


# ─── Lifecycle ────────────────────────────────────────────────────────────────

class LifecycleTests(SubscriptionTestBase):
    def test_full_happy_path_records_every_change(self):
        sub = self.make_active()
        services.pause_subscription(sub, actor=self.staff)
        services.resume_subscription(sub, actor=self.staff)
        services.close_subscription(sub, actor=self.staff)
        self.assertEqual(self.history(sub), [
            ("", Status.DRAFT), (Status.DRAFT, Status.QUOTATION), (Status.QUOTATION, Status.CONFIRMED),
            (Status.CONFIRMED, Status.ACTIVE), (Status.ACTIVE, Status.PAUSED), (Status.PAUSED, Status.ACTIVE),
            (Status.ACTIVE, Status.CLOSED),
        ])
        self.assertTrue(all(c.changed_by == self.staff for c in sub.status_changes.all()))

    def test_send_quote_sets_default_expiry(self):
        sub = self.make()
        services.send_quote(sub, actor=self.staff)
        self.assertEqual(sub.status, Status.QUOTATION)
        self.assertEqual(sub.quotation_expiry, TODAY + timedelta(days=services.DEFAULT_QUOTE_VALIDITY_DAYS))

    def test_send_quote_only_from_draft(self):
        sub = self.make_active()
        with self.assertRaises(services.SubscriptionError):
            services.send_quote(sub, actor=self.staff)

    def test_customer_cannot_send_quote_or_activate(self):
        sub = self.make()
        with self.assertRaises(services.SubscriptionError):
            services.send_quote(sub, actor=self.customer)
        services.send_quote(sub, actor=self.staff)
        services.confirm_subscription(sub, actor=self.customer)    # customer accepts own quote
        with self.assertRaises(services.SubscriptionError):
            services.activate_subscription(sub, actor=self.customer)

    def test_valid_quotation_can_be_confirmed(self):
        sub = self.make()
        services.send_quote(sub, actor=self.staff)
        services.confirm_subscription(sub, actor=self.staff)
        self.assertEqual(sub.status, Status.CONFIRMED)

    def test_expired_quotation_cannot_be_confirmed_and_reverts_to_draft(self):
        sub = self.make()
        services.send_quote(sub, actor=self.staff)
        Subscription.objects.filter(pk=sub.pk).update(quotation_expiry=TODAY - timedelta(days=1))
        with self.assertRaisesMessage(services.SubscriptionError, "expired"):
            services.confirm_subscription(sub, actor=self.staff)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Status.DRAFT)
        last = sub.status_changes.last()
        self.assertEqual((last.from_status, last.to_status, last.changed_by), (Status.QUOTATION, Status.DRAFT, None))

    def test_quotation_valid_on_its_expiry_day(self):
        sub = self.make()
        services.send_quote(sub, actor=self.staff)
        Subscription.objects.filter(pk=sub.pk).update(quotation_expiry=TODAY)
        services.confirm_subscription(sub, actor=self.staff)
        self.assertEqual(sub.status, Status.CONFIRMED)

    def test_expire_quotations_bulk(self):
        subs = [self.make() for _ in range(2)]
        for sub in subs:
            services.send_quote(sub, actor=self.staff)
        Subscription.objects.filter(pk=subs[0].pk).update(quotation_expiry=TODAY - timedelta(days=3))
        self.assertEqual(services.expire_quotations(), 1)
        self.assertEqual(Subscription.objects.get(pk=subs[0].pk).status, Status.DRAFT)
        self.assertEqual(Subscription.objects.get(pk=subs[1].pk).status, Status.QUOTATION)

    def test_activate_sets_first_billing_date_to_start(self):
        start = TODAY + timedelta(days=5)
        sub = self.make_active(start_date=start)
        self.assertEqual(sub.status, Status.ACTIVE)
        self.assertEqual(sub.next_billing_date, start)

    def test_activate_only_from_confirmed(self):
        sub = self.make()
        with self.assertRaises(services.SubscriptionError):
            services.activate_subscription(sub, actor=self.staff)
        self.assertEqual(self.history(sub), [("", Status.DRAFT)])   # failed actions leave no history

    def test_pause_only_when_plan_allows(self):
        sub = self.make_active(plan=self.locked_plan)
        with self.assertRaisesMessage(services.SubscriptionError, "doesn't allow pausing"):
            services.pause_subscription(sub, actor=self.staff)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Status.ACTIVE)

    def test_pause_only_from_active(self):
        sub = self.make()
        with self.assertRaises(services.SubscriptionError):
            services.pause_subscription(sub, actor=self.staff)

    def test_resume_after_expiry_is_rejected(self):
        sub = self.make_active(start_date=TODAY - timedelta(days=60), expiry_date=TODAY + timedelta(days=1))
        services.pause_subscription(sub, actor=self.staff)
        Subscription.objects.filter(pk=sub.pk).update(expiry_date=TODAY - timedelta(days=1))
        with self.assertRaisesMessage(services.SubscriptionError, "Renew"):
            services.resume_subscription(sub, actor=self.staff)

    def test_renew_extends_by_original_term(self):
        start = TODAY - timedelta(days=10)
        expiry = start.replace(year=start.year + 1) - timedelta(days=1)    # one-year term
        sub = self.make_active(start_date=start, expiry_date=expiry)
        services.renew_subscription(sub, actor=self.staff)
        self.assertEqual(sub.expiry_date, expiry.replace(year=expiry.year + 1))
        self.assertEqual(sub.status_changes.last().to_status, Status.ACTIVE)
        self.assertIn("Renewed", sub.status_changes.last().reason)

    def test_renew_only_when_plan_allows(self):
        sub = self.make_active(plan=self.locked_plan, expiry_date=TODAY + timedelta(days=30))
        with self.assertRaisesMessage(services.SubscriptionError, "doesn't allow renewal"):
            services.renew_subscription(sub, actor=self.staff)

    def test_renew_closed_subscription_reactivates_it(self):
        sub = self.make_active(start_date=TODAY - timedelta(days=40), expiry_date=TODAY + timedelta(days=1))
        Subscription.objects.filter(pk=sub.pk).update(expiry_date=TODAY - timedelta(days=10))
        services.close_subscription(sub, actor=self.staff)
        services.renew_subscription(sub, actor=self.staff)
        self.assertEqual(sub.status, Status.ACTIVE)
        self.assertEqual(sub.next_billing_date, TODAY)
        self.assertGreater(sub.expiry_date, TODAY)

    def test_close_before_expiry_needs_closable_plan(self):
        sub = self.make_active(plan=self.locked_plan, start_date=TODAY - timedelta(days=30),
                               expiry_date=TODAY + timedelta(days=30))
        with self.assertRaisesMessage(services.SubscriptionError, "before the expiry"):
            services.close_subscription(sub, actor=self.staff)
        Subscription.objects.filter(pk=sub.pk).update(expiry_date=TODAY - timedelta(days=1))
        services.close_subscription(sub, actor=self.staff)
        self.assertEqual(sub.status, Status.CLOSED)
        self.assertIsNone(sub.next_billing_date)

    def test_closed_cannot_be_closed_again(self):
        sub = self.make()
        services.close_subscription(sub, actor=self.staff)
        with self.assertRaises(services.SubscriptionError):
            services.close_subscription(sub, actor=self.staff)

    def test_customer_cannot_act_on_another_customers_subscription(self):
        sub = self.make_active()
        with self.assertRaisesMessage(services.SubscriptionError, "your own"):
            services.pause_subscription(sub, actor=self.other)

    def test_model_wrappers_raise_value_error_for_portal(self):
        sub = self.make()
        with self.assertRaises(ValueError):
            sub.pause()


class AutoCloseTests(SubscriptionTestBase):
    def _expired(self, plan):
        sub = self.make_active(plan=plan, start_date=TODAY - timedelta(days=60),
                               expiry_date=TODAY + timedelta(days=1))
        Subscription.objects.filter(pk=sub.pk).update(expiry_date=TODAY - timedelta(days=1))
        return sub

    def test_closes_only_expired_auto_close_subscriptions(self):
        expired_auto = self._expired(self.auto_plan)
        expired_manual = self._expired(self.plan)
        current_auto = self.make_active(plan=self.auto_plan, expiry_date=TODAY + timedelta(days=5))

        closed = services.close_expired_subscriptions()

        self.assertEqual(closed, [expired_auto.number])
        statuses = dict(Subscription.objects.values_list("pk", "status"))
        self.assertEqual(statuses[expired_auto.pk], Status.CLOSED)
        self.assertEqual(statuses[expired_manual.pk], Status.ACTIVE)
        self.assertEqual(statuses[current_auto.pk], Status.ACTIVE)
        change = expired_auto.status_changes.last()
        self.assertIsNone(change.changed_by)
        self.assertIn("auto-close", change.reason)

    def test_paused_subscriptions_are_closed_too(self):
        sub = self._expired(self.auto_plan)
        Subscription.objects.filter(pk=sub.pk).update(status=Status.PAUSED)
        self.assertEqual(services.close_expired_subscriptions(), [sub.number])

    def test_management_command_uses_the_same_rules(self):
        sub = self._expired(self.auto_plan)
        out = StringIO()
        call_command("close_expired_subscriptions", stdout=out)
        self.assertIn("Subscriptions closed: 1", out.getvalue())
        self.assertIn(sub.number, out.getvalue())
        self.assertEqual(Subscription.objects.get(pk=sub.pk).status, Status.CLOSED)
        out = StringIO()
        call_command("close_expired_subscriptions", stdout=out)   # idempotent
        self.assertIn("Subscriptions closed: 0", out.getvalue())


class TemplateTests(SubscriptionTestBase):
    def setUp(self):
        self.template = QuotationTemplate.objects.create(name="CRM starter", plan=self.plan, validity_days=7,
                                                         duration_months=12)
        TemplateLine.objects.create(template=self.template, product=self.product, variant=self.variant, quantity=3)
        TemplateLine.objects.create(template=self.template, product=self.addon, quantity=2,
                                    unit_price=Decimal("150.00"))

    def test_create_from_template_copies_plan_lines_and_term(self):
        start = TODAY
        sub = services.create_from_template(self.template, customer=self.customer, start_date=start,
                                            actor=self.staff)
        self.assertEqual((sub.plan, sub.template, sub.status), (self.plan, self.template, Status.DRAFT))
        self.assertEqual(sub.expiry_date, start.replace(year=start.year + 1) - timedelta(days=1))
        self.assertEqual(
            list(sub.lines.values_list("product__name", "quantity", "unit_price")),
            [("CRM Suite", 3, Decimal("1360.00")), ("Extra Storage", 2, Decimal("150.00"))],
        )

    def test_quote_from_template_uses_template_validity(self):
        sub = services.create_from_template(self.template, customer=self.customer, start_date=TODAY)
        services.send_quote(sub, actor=self.staff)
        self.assertEqual(sub.quotation_expiry, TODAY + timedelta(days=7))

    def test_editing_template_later_does_not_change_subscription(self):
        sub = services.create_from_template(self.template, customer=self.customer, start_date=TODAY)
        self.template.lines.update(quantity=10)
        self.template.lines.first().delete()
        self.assertEqual(list(sub.lines.values_list("quantity", flat=True)), [3, 2])

    def test_archived_template_cannot_be_used(self):
        self.template.is_active = False
        self.template.save()
        with self.assertRaises(services.SubscriptionError):
            services.create_from_template(self.template, customer=self.customer, start_date=TODAY)


# ─── API ──────────────────────────────────────────────────────────────────────

class SubscriptionAPITests(SubscriptionTestBase):
    url = "/api/subscriptions/"

    def setUp(self):
        self.client = APIClient()
        self.mine = self.make_active()
        self.theirs = self.make(customer=self.other)

    def as_user(self, user):
        self.client.force_authenticate(user)
        return self.client

    def numbers(self, response):
        return [row["number"] for row in response.json()["results"]]

    def test_anonymous_is_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_customer_sees_only_own_subscriptions(self):
        response = self.as_user(self.customer).get(self.url)
        self.assertEqual(self.numbers(response), [self.mine.number])

    def test_customer_gets_404_for_another_customers_subscription(self):
        client = self.as_user(self.customer)
        self.assertEqual(client.get(f"{self.url}{self.theirs.pk}/").status_code, 404)
        self.assertEqual(client.post(f"{self.url}{self.theirs.pk}/close/").status_code, 404)
        self.assertEqual(client.get(f"{self.url}{self.theirs.pk}/history/").status_code, 404)

    def test_customer_can_pause_own_subscription(self):
        response = self.as_user(self.customer).post(f"{self.url}{self.mine.pk}/pause/", {"reason": "Holiday"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Status.PAUSED)
        self.assertEqual(self.mine.status_changes.last().changed_by, self.customer)

    def test_customer_cannot_create_send_quote_or_activate(self):
        client = self.as_user(self.other)
        payload = {"customer": self.other.pk, "plan": self.plan.pk, "start_date": str(TODAY),
                   "lines": [{"product": self.product.pk, "quantity": 2}]}
        self.assertEqual(client.post(self.url, payload, format="json").status_code, 403)
        self.assertEqual(client.post(f"{self.url}{self.theirs.pk}/send-quote/").status_code, 403)
        self.assertEqual(client.post(f"{self.url}{self.theirs.pk}/activate/").status_code, 403)
        self.assertEqual(client.post(f"{self.url}close-expired/").status_code, 403)

    def test_staff_creates_subscription_number_from_backend(self):
        payload = {"customer": self.customer.pk, "plan": self.plan.pk, "start_date": str(TODAY),
                   "number": "HACK-1", "lines": [{"product": self.product.pk, "quantity": 4}]}
        response = self.as_user(self.staff).post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["number"], "SUB-0003")
        self.assertEqual(body["status"], Status.DRAFT)
        self.assertEqual(body["total"], "3776.00")     # 4 × 800 + 18%

    def test_create_validation_errors_are_400(self):
        payload = {"customer": self.customer.pk, "plan": self.plan.pk, "start_date": str(TODAY),
                   "lines": [{"product": self.product.pk, "quantity": 1}]}
        response = self.as_user(self.staff).post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("lines", response.json())
        payload["customer"] = self.staff.pk
        self.assertEqual(self.as_user(self.staff).post(self.url, payload, format="json").status_code, 400)

    def test_staff_edits_draft_only(self):
        client = self.as_user(self.staff)
        response = client.patch(f"{self.url}{self.theirs.pk}/", {"notes": "Call first"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["notes"], "Call first")
        response = client.patch(f"{self.url}{self.mine.pk}/", {"notes": "x"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_lifecycle_through_api(self):
        client = self.as_user(self.staff)
        base = f"{self.url}{self.theirs.pk}"
        response = client.post(f"{base}/send-quote/", {"validity_days": 10}, format="json")
        self.assertEqual(response.json()["quotation_expiry"], str(TODAY + timedelta(days=10)))
        self.assertEqual(client.post(f"{base}/confirm/").json()["status"], Status.CONFIRMED)
        self.assertEqual(client.post(f"{base}/activate/").json()["status"], Status.ACTIVE)
        history = client.get(f"{base}/history/").json()
        self.assertEqual([h["to_status"] for h in history],
                         [Status.DRAFT, Status.QUOTATION, Status.CONFIRMED, Status.ACTIVE])
        self.assertEqual(history[-1]["changed_by_name"], "Staff")

    def test_invalid_action_returns_400_and_changes_nothing(self):
        response = self.as_user(self.staff).post(f"{self.url}{self.theirs.pk}/activate/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("draft", response.json()["detail"])
        self.assertEqual(SubscriptionStatusChange.objects.filter(subscription=self.theirs).count(), 1)

    def test_search_and_filters(self):
        client = self.as_user(self.staff)
        self.assertEqual(self.numbers(client.get(self.url, {"search": self.mine.number})), [self.mine.number])
        self.assertEqual(self.numbers(client.get(self.url, {"search": "ravi"})), [self.theirs.number])
        self.assertEqual(self.numbers(client.get(self.url, {"status": "active"})), [self.mine.number])
        self.assertEqual(self.numbers(client.get(self.url, {"plan": self.locked_plan.pk})), [])
        self.assertEqual(self.numbers(client.get(self.url, {"customer": self.other.pk})), [self.theirs.number])

    def test_listing_reverts_expired_quotations(self):
        services.send_quote(self.theirs, actor=self.staff)
        Subscription.objects.filter(pk=self.theirs.pk).update(quotation_expiry=TODAY - timedelta(days=1))
        response = self.as_user(self.staff).get(self.url, {"customer": self.other.pk})
        self.assertEqual(response.json()["results"][0]["status"], Status.DRAFT)

    def test_close_expired_endpoint(self):
        sub = self.make_active(plan=self.auto_plan, start_date=TODAY - timedelta(days=30),
                               expiry_date=TODAY + timedelta(days=1))
        Subscription.objects.filter(pk=sub.pk).update(expiry_date=TODAY - timedelta(days=1))
        response = self.as_user(self.admin).post(f"{self.url}close-expired/")
        self.assertEqual(response.json(), {"closed": [sub.number], "count": 1})


class QuotationTemplateAPITests(SubscriptionTestBase):
    url = "/api/subscriptions/quotation-templates/"

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def payload(self, **overrides):
        data = {"name": "CRM starter", "plan": self.plan.pk, "validity_days": 14,
                "lines": [{"product": self.product.pk, "quantity": 2},
                          {"product": self.addon.pk, "quantity": 3, "unit_price": "99.00"}]}
        data.update(overrides)
        return data

    def test_create_edit_view_and_use_template(self):
        response = self.client.post(self.url, self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        template_id = response.json()["id"]

        response = self.client.patch(f"{self.url}{template_id}/",
                                     {"lines": [{"product": self.product.pk, "quantity": 5}]}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["lines"]), 1)
        self.assertEqual(self.client.get(f"{self.url}{template_id}/").json()["lines"][0]["quantity"], 5)

        response = self.client.post(f"{self.url}{template_id}/create-subscription/",
                                    {"customer": self.customer.pk, "start_date": str(TODAY)}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["template"], template_id)
        self.assertEqual(response.json()["lines"][0]["quantity"], 5)

    def test_template_lines_respect_plan_minimum(self):
        response = self.client.post(self.url, self.payload(lines=[{"product": self.product.pk, "quantity": 1}]),
                                    format="json")
        self.assertEqual(response.status_code, 400)

    def test_customers_cannot_use_templates(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class StaffPageTests(SubscriptionTestBase):
    def test_list_detail_and_action_buttons(self):
        sub = self.make()
        self.client.force_login(self.staff)
        self.assertContains(self.client.get("/subscriptions/", {"q": sub.number}), sub.number)
        page = self.client.get(f"/subscriptions/{sub.pk}/")
        self.assertContains(page, "Send quote")
        self.assertContains(page, "Status history")

        response = self.client.post(f"/subscriptions/{sub.pk}/send-quote/", follow=True)
        self.assertContains(response, "is now quotation")
        response = self.client.post(f"/subscriptions/{sub.pk}/activate/", follow=True)
        self.assertContains(response, "Can&#x27;t activate")
        sub.refresh_from_db()
        self.assertEqual(sub.status, Status.QUOTATION)

    def test_customers_cannot_open_staff_pages(self):
        sub = self.make()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(f"/subscriptions/{sub.pk}/").status_code, 403)
        self.assertEqual(self.client.post(f"/subscriptions/{sub.pk}/close/").status_code, 403)
