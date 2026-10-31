"""
accounts/views_web.py
Template-rendered pages: role-based home dispatcher, login, logout, signup.
Separate from views.py, which holds the JSON API endpoints.
"""

from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect

from .forms import SignUpForm, StyledAuthenticationForm


def home(request):
    """Entry point after login — sends each role to its landing page."""
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.role in ("admin", "staff"):
        return redirect("dashboard:index")
    return redirect("portal:my_subscriptions")


def login_page(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")

    form = StyledAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        messages.success(request, f"Welcome back, {form.get_user().first_name or form.get_user().username}.")
        return redirect("accounts:home")

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_page(request):
    auth_logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("accounts:login")


def signup_page(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        auth_login(request, user)
        messages.success(request, "Account created — welcome to Brightloop.")
        return redirect("accounts:home")

    return render(request, "accounts/signup.html", {"form": form})
