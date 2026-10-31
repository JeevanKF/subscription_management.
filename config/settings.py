"""
Django settings for Brightloop SMS.

Pages are server-rendered Django templates. The /api/ routes (DRF) are kept
for the React frontend. Secrets and database settings come from .env.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Base dir & .env ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ─── Python Executable Path ───────────────────────────────────────────────────
PYTHON_EXECUTABLE = os.environ.get(
    "PYTHON_EXECUTABLE",
    r"C:\Users\lenovo\AppData\Local\Programs\Python\Python313\python.exe",
)

# ─── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

# ─── Custom user (must be set before first migration) ─────────────────────────
AUTH_USER_MODEL = "accounts.User"

# ─── Installed apps ───────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    # Brightloop apps — order matches dependency direction
    "accounts",
    "products",
    "subscriptions",
    "billing",
    "dashboard",
    "portal",
]

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",          # must be first
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "billing.context_processors.overdue_count",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ─── Database — PostgreSQL from .env ──────────────────────────────────────────
# Uses PostgreSQL when DB_NAME or DB_HOST is set in .env (local server or Neon).
# Otherwise falls back to a local SQLite file so the project still runs (and
# tests still pass) on a machine without PostgreSQL.
if os.environ.get("DB_NAME") or os.environ.get("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "brightloop"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "OPTIONS": {
                "sslmode": os.environ.get("DB_SSLMODE", "prefer"),
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# ─── CORS — allow React dev server ────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite default
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True

# ─── Auth ─────────────────────────────────────────────────────────────────────
# Login is by email, case-insensitive (see UserManager.get_by_natural_key).
# One rule for sign-up, staff creation and password reset: see accounts/validators.py
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "accounts.validators.StrongPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:home"      # sends each role to its own home page
LOGOUT_REDIRECT_URL = "accounts:login"

# Password reset links expire after 1 day (or after first use)
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ─── Static files ─────────────────────────────────────────────────────────────
STATIC_URL = "/static/"

# ─── Email — console backend for dev (reset links print in the terminal) ──────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Brightloop SMS <no-reply@brightloop.local>"

# ─── Default primary key ──────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
