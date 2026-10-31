# Accounts & Products (M2)

What this part of Brightloop SMS does, and how to run it.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # fill in PostgreSQL details, or leave DB_NAME empty to use SQLite
python manage.py migrate
python manage.py createsuperuser   # this first user gets the Admin role
python manage.py runserver
```

Open http://127.0.0.1:8000/ and log in with the email and password you just chose.
Password reset and "set your password" emails are **printed in the terminal** running `runserver`.

Run the tests:

```bash
python manage.py test accounts products
```

## Pages

| URL | Who | What |
|---|---|---|
| `/` | Logged in | Sends Admin/Staff to the dashboard, Customers to the portal (a simple home page until those apps exist) |
| `/accounts/signup/` | Public | Customer sign-up (role is always customer) |
| `/accounts/login/`, `/accounts/logout/` | Public | Login with email (case-insensitive); logout is a POST button in the navbar |
| `/accounts/password-reset/` | Public | Forgot password; link valid once, for 1 day |
| `/accounts/staff/`, `/accounts/staff/new/` | Admin | List and create staff |
| `/accounts/customers/` (+ `new/`, `<id>/`, `export/`) | Admin, Staff | Search, create, edit, CSV export. New customers get an email link to set their password |
| `/products/` (+ `new/`, `<id>/`, `<id>/edit/`, `<id>/delete/`) | Admin edits, Staff views | Products with inline variants |
| `/products/plans/…` | Admin edits, Staff views | Plans |
| `/products/taxes/…` | Admin edits, Staff views | Tax rules |

## For teammates: things you can import

```python
from accounts.decorators import role_required      # @role_required("admin", "staff")
from accounts.exports import export_csv            # export_csv("x.csv", rows, [("Header", "field.path"), ...])
from accounts.forms import BootstrapFormMixin      # adds Bootstrap classes to any form
from products.models import Plan, validate_plan_available
Plan.objects.available()                           # plans that can be picked today
validate_plan_available(plan, on_date)             # raises "This plan isn't available on that date."
```

Templates: `{% include "accounts/_form_fields.html" %}` renders a form with errors next to fields;
`{% include "accounts/_pagination.html" %}` renders pagination for a `page` object.

`accounts/test_access.py` checks every accounts/products URL for anonymous, customer, staff and admin.
Copy the pattern for your app's URLs.

## Changes outside my apps (tell the owners)

- **User model**: login is by `email`; there is no `username`, `first_name` or `last_name` any more, use `user.name`.
  `subscriptions/serializers.py` was updated (`customer.username` → `customer.name`).
- **Products**: `Variant` is now `ProductVariant` (the old name still imports). `Plan.billing_cycle` is now
  `billing_period` (daily/weekly/monthly/yearly). `TaxRule` lives in `products`.
- **templates/base.html** (M4): navbar links to apps that don't have pages yet are hidden instead of crashing;
  added Catalog, Customers and Staff links; logout is now a POST form (required by Django 5).
- **config/urls.py**: pages mounted at `/` and `/products/`; the Django admin moved to `/django-admin/`;
  the REST API stays under `/api/…` (now in `accounts/api_urls.py` and `products/api_urls.py`).
- **Database**: settings read PostgreSQL from `.env`; with no `DB_NAME` they fall back to SQLite.
  New migrations: `accounts/0002`, `0003` and `products/0002`, `0003`. Run `python manage.py migrate`.
