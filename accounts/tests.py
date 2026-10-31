from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .exports import export_csv
from .models import User
from .validators import PASSWORD_ERROR, StrongPasswordValidator, validate_phone

GOOD_PASSWORD = "Test-pass-123!"


class PasswordValidatorTests(TestCase):
    def test_rejects_weak_passwords(self):
        for password in ["Short1!", "Abcdefg!", "alllower-123", "ALLUPPER-123", "NoSpecial123"]:
            with self.subTest(password=password), self.assertRaisesMessage(ValidationError, PASSWORD_ERROR):
                StrongPasswordValidator().validate(password)

    def test_accepts_strong_password(self):
        StrongPasswordValidator().validate("Abcdefg1!")  # 9 characters
        StrongPasswordValidator().validate(GOOD_PASSWORD)

    def test_phone(self):
        validate_phone("+91 98765 43210")
        validate_phone("")
        for bad in ["12345", "phone-123456", "1234567890123456"]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_phone(bad)


class SignUpLoginTests(TestCase):
    def signup(self, **overrides):
        data = {"name": "Asha", "email": "Asha@Example.com",
                "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD}
        data.update(overrides)
        return self.client.post(reverse("accounts:signup"), data)

    def test_signup_creates_logged_in_customer(self):
        response = self.signup(role="admin")  # a posted role must be ignored
        self.assertEqual(response.status_code, 302)
        user = User.objects.get()
        self.assertEqual(user.email, "asha@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_email_is_unique_ignoring_case(self):
        self.signup()
        self.client.logout()
        response = self.signup(email="ASHA@example.COM")
        self.assertContains(response, "An account with this email already exists.")
        self.assertEqual(User.objects.count(), 1)

    def test_password_rules_and_confirmation(self):
        self.assertContains(self.signup(password1="weak", password2="weak"), PASSWORD_ERROR)
        self.assertContains(self.signup(password2="Different-123!"), "Passwords don&#x27;t match.")
        self.assertFalse(User.objects.exists())

    def test_login_is_case_insensitive_and_goes_home(self):
        User.objects.create_user("asha@example.com", GOOD_PASSWORD, name="Asha")
        response = self.client.post(reverse("accounts:login"),
                                    {"username": "ASHA@example.com", "password": GOOD_PASSWORD})
        self.assertRedirects(response, reverse("accounts:home"), fetch_redirect_response=False)

    def test_wrong_password_shows_error(self):
        User.objects.create_user("asha@example.com", GOOD_PASSWORD, name="Asha")
        response = self.client.post(reverse("accounts:login"),
                                    {"username": "asha@example.com", "password": "nope"})
        self.assertContains(response, "Incorrect email or password.")

    def test_each_role_gets_a_home_page(self):
        for role in User.Role.values:
            user = User.objects.create_user(f"{role}@example.com", GOOD_PASSWORD, name=role, role=role)
            self.client.force_login(user)
            response = self.client.get(reverse("accounts:home"))
            # 302 once the dashboard/portal apps have pages, 200 (fallback home) until then
            self.assertIn(response.status_code, (200, 302))

    def test_logout(self):
        self.client.force_login(User.objects.create_user("a@example.com", GOOD_PASSWORD, name="A"))
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetTests(TestCase):
    def test_link_expires_after_one_day(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 60 * 60 * 24)

    def test_reset_flow(self):
        User.objects.create_user("asha@example.com", GOOD_PASSWORD, name="Asha")
        self.client.post(reverse("accounts:password_reset"), {"email": "asha@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        link = next(line for line in mail.outbox[0].body.splitlines() if "/password-reset/" in line)
        path = link.split("testserver", 1)[1].strip()
        response = self.client.get(path, follow=True)  # Django swaps the token into the session
        self.assertTrue(response.context["validlink"])
        response = self.client.post(response.redirect_chain[-1][0],
                                    {"new_password1": "New-pass-456!", "new_password2": "New-pass-456!"})
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.assertTrue(self.client.login(username="asha@example.com", password="New-pass-456!"))


class StaffAndCustomerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin@example.com", GOOD_PASSWORD, name="Admin", role="admin")
        cls.staff = User.objects.create_user("staff@example.com", GOOD_PASSWORD, name="Staff", role="staff")

    def test_admin_creates_staff(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("accounts:staff_create"), {
            "name": "New Staff", "email": "new@example.com",
            "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD,
        })
        self.assertEqual(User.objects.get(email="new@example.com").role, User.Role.STAFF)

    def test_staff_cannot_create_staff(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("accounts:staff_create"), {
            "name": "X", "email": "x@example.com", "password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email="x@example.com").exists())

    def test_staff_creates_customer_who_sets_password_by_link(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("accounts:customer_create"), {
            "name": "Ravi", "email": "Ravi@Example.com", "company": "Acme", "phone": "+91 98765 43210",
        })
        customer = User.objects.get(email="ravi@example.com")
        self.assertEqual(customer.role, User.Role.CUSTOMER)
        self.assertFalse(customer.has_usable_password())
        self.assertEqual(mail.outbox[0].to, ["ravi@example.com"])

        link = next(line for line in mail.outbox[0].body.splitlines() if "/password-reset/" in line)
        self.client.logout()
        response = self.client.get(link.split("testserver", 1)[1].strip(), follow=True)
        self.client.post(response.redirect_chain[-1][0],
                         {"new_password1": "Ravi-pass-789!", "new_password2": "Ravi-pass-789!"})
        self.assertTrue(self.client.login(username="ravi@example.com", password="Ravi-pass-789!"))

    def test_customer_search_and_edit(self):
        a = User.objects.create_user("a@example.com", None, name="Alpha Traders", company="Alpha")
        User.objects.create_user("b@example.com", None, name="Beta Co")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:customer_list"), {"q": "alpha"})
        self.assertEqual([c.pk for c in response.context["page"]], [a.pk])

        self.client.post(reverse("accounts:customer_detail", args=[a.pk]), {
            "name": "Alpha Ltd", "email": "a@example.com", "company": "Alpha", "phone": "",
            "address": "", "is_active": "on",
        })
        a.refresh_from_db()
        self.assertEqual(a.name, "Alpha Ltd")

    def test_staff_page_cannot_open_staff_as_customer(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:customer_detail", args=[self.staff.pk]))
        self.assertEqual(response.status_code, 404)

    def test_customer_export(self):
        User.objects.create_user("c@example.com", None, name="=SUM(A1)", company="Gamma")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:customer_export"))
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        body = response.content.decode("utf-8-sig")
        self.assertIn("ID,Name,Email,Company,Phone,Address,Active,Joined", body)
        self.assertIn("'=SUM(A1),c@example.com,Gamma", body)   # formulas are neutralised
        self.assertNotIn("staff@example.com", body)              # customers only


class ExportHelperTests(TestCase):
    def test_accessors(self):
        user = User(pk=7, name="Asha", email="asha@example.com", is_active=True)
        response = export_csv("x.csv", [user], [
            ("ID", "pk"), ("Name", "name"), ("Short", "get_short_name"), ("Upper", lambda u: u.name.upper()),
            ("Active", "is_active"),
        ])
        self.assertEqual(response.content.decode("utf-8-sig").splitlines()[1], "7,Asha,Asha,ASHA,Yes")
