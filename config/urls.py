"""
Root URL configuration for Brightloop SMS.
All /api/* routes go to app-level API routers.
Django admin stays at /admin/.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Template-rendered web UI
    path("", include("accounts.web_urls")),
    path("products/", include("products.web_urls")),
    path("subscriptions/", include("subscriptions.web_urls")),
    path("billing/", include("billing.web_urls")),
    path("dashboard/", include("dashboard.web_urls")),

    # REST API routes
    path("api/auth/",          include("accounts.urls")),
    path("api/products/",      include("products.urls")),
    path("api/subscriptions/", include("subscriptions.urls")),
    path("api/billing/",       include("billing.urls")),
    path("api/dashboard/",     include("dashboard.urls")),
    path("api/portal/",        include("portal.urls")),

    # DRF browsable API auth (login/logout in browser)
    path("api-auth/", include("rest_framework.urls")),
]
