"""accounts/urls.py — server-rendered pages. The JSON API is in api_urls.py."""
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import EmailLoginForm, NewPasswordForm, ResetPasswordForm

app_name = "accounts"

urlpatterns = [
    path("", views.home, name="home"),

    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/login/", auth_views.LoginView.as_view(
        authentication_form=EmailLoginForm,
        redirect_authenticated_user=True,
    ), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),

    # Django's 4 built-in password reset pages. Links expire after 1 day (PASSWORD_RESET_TIMEOUT).
    path("accounts/password-reset/", auth_views.PasswordResetView.as_view(
        form_class=ResetPasswordForm,
        email_template_name="registration/password_reset_email.txt",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    ), name="password_reset"),
    path("accounts/password-reset/sent/", auth_views.PasswordResetDoneView.as_view(),
         name="password_reset_done"),
    path("accounts/password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        form_class=NewPasswordForm,
        success_url=reverse_lazy("accounts:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("accounts/password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(),
         name="password_reset_complete"),

    path("accounts/staff/", views.staff_list, name="staff_list"),
    path("accounts/staff/new/", views.staff_create, name="staff_create"),

    path("accounts/customers/", views.customer_list, name="customer_list"),
    path("accounts/customers/new/", views.customer_create, name="customer_create"),
    path("accounts/customers/export/", views.customer_export, name="customer_export"),
    path("accounts/customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("accounts/customers/<int:pk>/send-password-link/", views.customer_send_password_link,
         name="customer_send_password_link"),
]
