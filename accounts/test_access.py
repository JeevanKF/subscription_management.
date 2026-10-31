"""
Checks every URL in the accounts and products apps for each kind of visitor:
anonymous, customer, staff and admin.

    anonymous on a protected page  -> 302 redirect to login
    logged in with the wrong role  -> 403
    allowed role                   -> 200 (or 302 after a POST action)

When you add a URL to accounts/ or products/, add it to ACCESS below;
test_every_url_is_covered fails until you do. Other apps can copy this pattern.
"""

from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from accounts.models import User
from products.models import Plan, Product, TaxRule

PUBLIC = "public"        # anyone; logged-in users may be redirected away (login, sign-up)
HOME = "home"            # anyone logged in; anonymous goes to login
REDIRECT = "redirect"    # always redirects (logout)
ADMIN = ("admin",)
ADMIN_STAFF = ("admin", "staff")

ROLES = ["anonymous", "customer", "staff", "admin"]
CHECKED_NAMESPACES = {"accounts", "products"}

# (url name, kwargs builder, rule, HTTP method)
ACCESS = [
    ("accounts:home", None, HOME, "get"),
    ("accounts:signup", None, PUBLIC, "get"),
    ("accounts:login", None, PUBLIC, "get"),
    ("accounts:logout", None, REDIRECT, "post"),
    ("accounts:password_reset", None, PUBLIC, "get"),
    ("accounts:password_reset_done", None, PUBLIC, "get"),
    ("accounts:password_reset_confirm", lambda t: {"uidb64": "MQ", "token": "bad-token"}, PUBLIC, "get"),
    ("accounts:password_reset_complete", None, PUBLIC, "get"),
    ("accounts:staff_list", None, ADMIN, "get"),
    ("accounts:staff_create", None, ADMIN, "get"),
    ("accounts:customer_list", None, ADMIN_STAFF, "get"),
    ("accounts:customer_create", None, ADMIN_STAFF, "get"),
    ("accounts:customer_export", None, ADMIN_STAFF, "get"),
    ("accounts:customer_detail", lambda t: {"pk": t.other_customer.pk}, ADMIN_STAFF, "get"),
    ("accounts:customer_send_password_link", lambda t: {"pk": t.other_customer.pk}, ADMIN_STAFF, "post"),

    ("products:list", None, ADMIN_STAFF, "get"),
    ("products:product_create", None, ADMIN, "get"),
    ("products:product_detail", lambda t: {"pk": t.product.pk}, ADMIN_STAFF, "get"),
    ("products:product_edit", lambda t: {"pk": t.product.pk}, ADMIN, "get"),
    ("products:product_delete", lambda t: {"pk": t.product.pk}, ADMIN, "get"),
    ("products:plan_list", None, ADMIN_STAFF, "get"),
    ("products:plan_create", None, ADMIN, "get"),
    ("products:plan_detail", lambda t: {"pk": t.plan.pk}, ADMIN_STAFF, "get"),
    ("products:plan_edit", lambda t: {"pk": t.plan.pk}, ADMIN, "get"),
    ("products:plan_delete", lambda t: {"pk": t.plan.pk}, ADMIN, "get"),
    ("products:tax_list", None, ADMIN_STAFF, "get"),
    ("products:tax_create", None, ADMIN, "get"),
    ("products:tax_edit", lambda t: {"pk": t.tax.pk}, ADMIN, "get"),
    ("products:tax_delete", lambda t: {"pk": t.tax.pk}, ADMIN, "get"),
]


def expected_status(rule, method, role):
    if rule == PUBLIC:
        return {200} if role == "anonymous" else {200, 302}
    if rule == HOME:
        return {302} if role == "anonymous" else {200, 302}
    if rule == REDIRECT:
        return {302}
    if role == "anonymous":
        return {302}
    if role in rule:
        return {302} if method == "post" else {200}
    return {403}


def named_urls(patterns, namespace=None):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from named_urls(p.url_patterns, p.namespace or namespace)
        elif isinstance(p, URLPattern) and p.name and namespace in CHECKED_NAMESPACES:
            yield f"{namespace}:{p.name}"


class UrlAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {
            "customer": User.objects.create_user("customer@example.com", "Test-pass-123!", name="Cust", role="customer"),
            "staff": User.objects.create_user("staff@example.com", "Test-pass-123!", name="Staff", role="staff"),
            "admin": User.objects.create_user("admin@example.com", "Test-pass-123!", name="Admin", role="admin"),
        }
        cls.other_customer = User.objects.create_user("other@example.com", "Test-pass-123!", name="Other")
        cls.tax = TaxRule.objects.create(name="GST 18%", rate="18.00")
        cls.product = Product.objects.create(name="CRM Suite", sales_price="1000.00", tax_rule=cls.tax)
        cls.plan = Plan.objects.create(name="Monthly", price="1000.00", product=cls.product)

    def test_every_url_is_covered(self):
        covered = {name for name, *_ in ACCESS}
        missing = set(named_urls(get_resolver().url_patterns)) - covered
        self.assertFalse(missing, f"Add these URLs to ACCESS in accounts/test_access.py: {sorted(missing)}")

    def test_access_for_every_role(self):
        for name, kwargs, rule, method in ACCESS:
            url = reverse(name, kwargs=kwargs(self) if kwargs else None)
            for role in ROLES:
                with self.subTest(url=url, role=role):
                    self.client.logout()
                    if role != "anonymous":
                        self.client.force_login(self.users[role])
                    response = getattr(self.client, method)(url)
                    self.assertIn(response.status_code, expected_status(rule, method, role))
                    if role == "anonymous" and response.status_code == 302 and rule not in (PUBLIC, REDIRECT):
                        self.assertTrue(response["Location"].startswith(reverse("accounts:login")))
