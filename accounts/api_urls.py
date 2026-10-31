"""accounts/api_urls.py — JSON API for the React frontend, mounted at /api/auth/."""
from django.urls import path
from . import api_views

urlpatterns = [
    path("health/",  api_views.health_check, name="health_check"),
    path("login/",   api_views.login_view,   name="auth_login"),
    path("logout/",  api_views.logout_view,  name="auth_logout"),
    path("me/",      api_views.me_view,      name="auth_me"),
]
