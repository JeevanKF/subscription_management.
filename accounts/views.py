"""
accounts/views.py
Server-rendered pages: sign-up, home redirect by role, staff and customer management.
Login, logout and password reset use Django's built-in views (see urls.py).
The JSON API for the React frontend lives in api_views.py.
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .decorators import role_required
from .exports import export_csv
from .forms import CustomerForm, SignUpForm, StaffCreateForm
from .models import User

PAGE_SIZE = 25

# Where each role lands after login. If the target app has no page yet,
# the user sees accounts/home.html instead.
ROLE_HOME = {
    User.Role.ADMIN: "dashboard:index",
    User.Role.STAFF: "dashboard:index",
    User.Role.CUSTOMER: "portal:my_subscriptions",
}


def home(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    try:
        return redirect(reverse(ROLE_HOME[request.user.role]))
    except (NoReverseMatch, KeyError):
        return render(request, "accounts/home.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to Brightloop, {user.name}!")
        return redirect("accounts:home")
    return render(request, "accounts/signup.html", {"form": form})


# ── Staff (admin only) ────────────────────────────────────────────────────────

@role_required("admin")
def staff_list(request):
    staff = User.objects.filter(role__in=[User.Role.ADMIN, User.Role.STAFF])
    page = Paginator(staff, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "accounts/staff_list.html", {"page": page})


@role_required("admin")
def staff_create(request):
    form = StaffCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Staff account created for {user.email}.")
        return redirect("accounts:staff_list")
    return render(request, "accounts/staff_form.html", {"form": form})


# ── Customers (admin and staff) ───────────────────────────────────────────────

def _search_customers(request):
    customers = User.objects.filter(role=User.Role.CUSTOMER)
    q = request.GET.get("q", "").strip()
    if q:
        customers = customers.filter(
            Q(name__icontains=q) | Q(email__icontains=q)
            | Q(company__icontains=q) | Q(phone__icontains=q)
        )
    return customers, q


def send_set_password_email(request, user):
    """Email a one-time link (valid 1 day) where the user chooses their password."""
    link = request.build_absolute_uri(reverse("accounts:password_reset_confirm", kwargs={
        "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }))
    body = render_to_string("accounts/emails/set_password.txt", {"user": user, "link": link})
    send_mail("Set your Brightloop password", body, None, [user.email])


@role_required("admin", "staff")
def customer_list(request):
    customers, q = _search_customers(request)
    page = Paginator(customers, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "accounts/customer_list.html", {"page": page, "q": q})


@role_required("admin", "staff")
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        send_set_password_email(request, customer)
        messages.success(
            request,
            f"Customer created. A link to set their password was emailed to {customer.email}.",
        )
        return redirect("accounts:customer_detail", pk=customer.pk)
    return render(request, "accounts/customer_form.html", {"form": form})


@role_required("admin", "staff")
def customer_detail(request, pk):
    customer = get_object_or_404(User, pk=pk, role=User.Role.CUSTOMER)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer saved.")
        return redirect("accounts:customer_detail", pk=customer.pk)
    return render(request, "accounts/customer_form.html", {"form": form, "customer": customer})


@role_required("admin", "staff")
@require_POST
def customer_send_password_link(request, pk):
    customer = get_object_or_404(User, pk=pk, role=User.Role.CUSTOMER)
    send_set_password_email(request, customer)
    messages.success(request, f"Password link emailed to {customer.email}.")
    return redirect("accounts:customer_detail", pk=customer.pk)


@role_required("admin", "staff")
def customer_export(request):
    customers, _ = _search_customers(request)
    return export_csv("customers.csv", customers, [
        ("ID", "pk"),
        ("Name", "name"),
        ("Email", "email"),
        ("Company", "company"),
        ("Phone", "phone"),
        ("Address", "address"),
        ("Active", "is_active"),
        ("Joined", "date_joined"),
    ])
