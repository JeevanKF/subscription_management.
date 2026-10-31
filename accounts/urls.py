"""accounts/urls.py"""
from django.urls import path
from . import views

urlpatterns = [
    path("health/",  views.health_check, name="health_check"),
    path("login/",   views.login_view,   name="auth_login"),
    path("logout/",  views.logout_view,  name="auth_logout"),
    path("me/",      views.me_view,      name="auth_me"),
]
