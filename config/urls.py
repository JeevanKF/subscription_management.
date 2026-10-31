"""
Root URL configuration for Brightloop SMS.
Server-rendered pages mount under their app prefix (one include() per app).
All /api/* routes go to app-level API routers for the React frontend.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Team debugging only, not part of the demo
    path("django-admin/", admin.site.urls),

    # Pages
    path("", include("accounts.urls")),
    path("products/", include("products.urls")),

    # Template-rendered web UI
    # accounts.web_urls and products.web_urls (M4) are not mounted: they reuse
    # the "accounts"/"products" namespaces that M2's pages above already serve.
    path("subscriptions/", include("subscriptions.web_urls")),
    path("billing/", include("billing.web_urls")),
    path("dashboard/", include("dashboard.web_urls")),
    path("portal/", include("portal.web_urls")),

    # REST API routes
    path("api/auth/",          include("accounts.api_urls")),
    path("api/products/",      include("products.api_urls")),
    path("api/subscriptions/", include("subscriptions.urls")),
    path("api/billing/",       include("billing.urls")),
    path("api/dashboard/",     include("dashboard.urls")),
    path("api/portal/",        include("portal.urls")),

    # DRF browsable API auth (login/logout in browser)
    path("api-auth/", include("rest_framework.urls")),
]
