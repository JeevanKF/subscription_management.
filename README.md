# Brightloop SMS

## Project Overview

Brightloop is a Subscription Management System designed to simplify and manage the complete subscription lifecycle of a business.

The application helps administrators and internal staff manage customers, products, subscription plans, quotations, subscriptions, invoices, payments, and discounts through a centralized platform.

Customers can access their own subscription details, view invoices, and track payment history through a customer portal.

The main objective is to reduce manual work, improve billing accuracy, and provide a clear overview of subscription-related business operations.

## Problem Statement

Managing subscriptions manually can lead to billing errors, missed payments, duplicate invoices, and difficulties tracking customer subscriptions.

Brightloop aims to solve these problems by providing a centralized system that manages the subscription lifecycle, automates recurring billing processes, and helps businesses monitor their subscription activities efficiently.

## Core Features

### 1. User Management
- User registration and login.
- Role-based access control.
- Separate access for administrators, internal staff, and customers.

### 2. Customer Management
- Add, view, update, and manage customer information.
- View customer subscription history.
- Track customer invoices and payments.

### 3. Product Management
- Create and manage products.
- Add product variants.
- Organize products for subscription plans.

### 4. Subscription Plan Management
- Create daily, weekly, monthly, and yearly plans.
- Configure subscription pricing.
- Manage plan availability and duration.

### 5. Subscription Management
- Create and manage customer subscriptions.
- Track subscription status.
- Support subscription activation, renewal, pause, and closure.

### 6. Quotation Management
- Create quotations for customers.
- Manage quotation details and status.
- Convert approved quotations into subscriptions.

### 7. Invoice Management
- Generate invoices for subscriptions.
- Calculate applicable taxes and discounts.
- Track paid, unpaid, and overdue invoices.
- Prevent duplicate billing.

### 8. Payment Management
- Record customer payments.
- Track payment history.
- Monitor outstanding balances.

### 9. Dashboard and Reports
- Display total customers and active subscriptions.
- Monitor revenue and outstanding payments.
- View subscription and payment statistics.
- Display business insights through charts and visualizations.

## User Roles

**Administrator**

Has complete access to manage users, products, plans, subscriptions, billing, payments, and business reports.

**Internal Staff**

Can manage assigned customers, quotations, subscriptions, invoices, and payments based on their permissions.

**Customer**

Can access their own account, view subscriptions, check invoices, and track payment history.

## Technology Stack

**Frontend:** React.js

**Database:** PostgreSQL

**Backend:** Backend/API layer (implementation to be specified)

**Version Control:** Git and GitHub

## System Architecture

The application follows a frontend–backend–database architecture.

The React frontend provides the user interface and allows users to interact with the application.

The backend/API layer handles business logic, authentication, subscription operations, billing calculations, and communication with the database.

PostgreSQL stores application data, including users, customers, products, subscription plans, subscriptions, invoices, and payments.

## Application Workflow

1. The administrator logs into the system.
2. Products and subscription plans are created.
3. Customers register or are added by internal staff.
4. Quotations are created when required.
5. Approved quotations are converted into subscriptions.
6. Subscriptions are activated.
7. Invoices are generated according to the subscription billing cycle.
8. Payments are recorded and tracked.
9. The dashboard displays subscription and financial information.

## Project Development Roadmap

### Phase 1 – Core Application Development

- Develop the React frontend.
- Set up the PostgreSQL database.
- Implement the backend/API integration.
- Develop authentication and role-based access.
- Implement customer, product, and plan management.
- Develop subscription and quotation management.
- Implement invoice and payment management.
- Build the main dashboard.

### Phase 2 – Automation and Improvements

- Automate recurring invoice generation.
- Improve subscription renewal and closure workflows.
- Implement automatic billing checks.
- Improve reporting and business analytics.
- Enhance application performance and user experience.


## Team Responsibilities

The project is developed collaboratively by a team of four members, with responsibilities divided across frontend development, backend development, database management, business logic, and integration.

All modules will be integrated into a single application.

> Subscription management system — Django REST API + React (Vite) frontend.

## Project structure

```
brightloop/
├── config/          # Django project (settings, urls, wsgi)
├── accounts/        # Custom User model, server-rendered auth/customers/staff pages, Token auth API
├── products/        # Product, Variant, Plan, TaxRule — server pages + API
├── subscriptions/   # Subscription lifecycle, quotation templates, status history — pages + API
├── billing/         # Invoice, InvoiceLine, Payment, Discount — pages + API
├── dashboard/       # Finance dashboard (server page + API) for admin/staff
├── portal/          # Customer self-service portal (server pages + API)
├── templates/       # Shared base.html (sidebar app shell) + 404/500/empty-state partials
├── frontend/        # Optional React (Vite) SPA for the same /api/* endpoints
│   └── src/
│       ├── api/         # Axios API modules per app
│       ├── context/     # AuthContext (token + user)
│       ├── components/  # Navbar, ProtectedRoute
│       └── pages/       # One page component per route
├── .env             # Local secrets — never commit (omit it entirely for SQLite)
├── .env.example     # Template
└── requirements.txt
```

## Local setup

The server-rendered pages (login, dashboard, products, subscriptions, billing,
customer portal — everything under `http://localhost:8000`, no npm required)
are the main app. The `frontend/` React SPA is a separate, optional client
for the same `/api/*` endpoints.

### 1. Backend — quickest path (SQLite, no database setup)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# Do NOT create a .env file for this path — with no .env, Django
# automatically falls back to a local db.sqlite3 file. No PostgreSQL
# install, no "database does not exist" errors, nothing else to configure.

python manage.py migrate
python manage.py seed_data         # demo tax rules, products, plans,
                                    # customers, subscriptions, invoices
python manage.py createsuperuser   # create an admin login
python manage.py runserver         # http://localhost:8000
```

Log in at `http://localhost:8000/accounts/login/` with the superuser you just
created (role = admin), or look up a seeded customer's email in the Django
shell and set a password for it if you want to see the customer portal.

**If a page 500s with `OperationalError: no such column ...` or similar:**
your local `db.sqlite3` predates a newer migration. It's just a local file
(it's gitignored, never shared) — delete it and re-run `migrate` + `seed_data`:

```bash
rm db.sqlite3            # del db.sqlite3   on Windows cmd
python manage.py migrate
python manage.py seed_data
```

### 2. Backend — PostgreSQL instead (optional)

Only do this if you specifically need Postgres. Copy `.env.example` to
`.env`, fill in `DB_NAME`/`DB_USER`/`DB_PASSWORD`, create that database in
Postgres first (`CREATE DATABASE brightloop;`), then run the same
`migrate` / `seed_data` / `createsuperuser` / `runserver` commands above.
Setting *any* of `DB_NAME` or `DB_HOST` in `.env` switches the app from
SQLite to Postgres — see `config/settings.py`.

### 3. Frontend (optional React SPA)

```bash
cd frontend
npm install
npm run dev    # runs on http://localhost:5173
```

Vite proxies all `/api/*` requests to Django on port 8000 — no CORS issues in
dev. The Django backend must already be running (step 1 or 2 above).

### Troubleshooting a teammate's machine

- **"No `.vscode`/python interpreter" errors in the editor:** that's an
  editor setting, not the app — point your IDE at your own `venv`
  (`venv\Scripts\python.exe` / `venv/bin/python`). `.vscode/` is gitignored
  now so this won't come from the repo.
- **`ModuleNotFoundError` for a Python package:** your venv wasn't active
  when you ran `pip install -r requirements.txt`, or you're running
  `python`/`manage.py` with a different interpreter than the one you
  installed into. Re-activate the venv and re-run `pip install`.
- **`npm error could not determine executable to run` / no `package.json`
  found in `frontend/`:** make sure you pulled the latest `main` —
  `frontend/package.json` is tracked in git (it used to be accidentally
  gitignored on some branches).
- **Blank/empty-looking pages after `runserver`:** you haven't run
  `seed_data` yet, or you're not logged in. Create a superuser (above) and
  log in at `/accounts/login/`.

## API endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/auth/health/` | PostgreSQL health check (public) |
| POST | `/api/auth/login/` | Get auth token |
| POST | `/api/auth/logout/` | Delete token |
| GET | `/api/auth/me/` | Current user profile |
| GET | `/api/products/` | Product list |
| GET/POST | `/api/subscriptions/` | Subscription list (search/filters) / create |
| POST | `/api/subscriptions/{id}/send-quote/` … `/close/` | Lifecycle actions (send-quote, confirm, activate, pause, resume, renew, close) |
| GET | `/api/subscriptions/{id}/history/` | Status history |
| CRUD | `/api/subscriptions/quotation-templates/` | Quotation templates (+ `/{id}/create-subscription/`) |
| GET/POST | `/api/billing/invoices/` | Invoice list |
| GET | `/api/dashboard/` | Finance summary (admin/staff) |
| GET | `/api/portal/subscriptions/` | Customer's own subscriptions |
| GET | `/api/portal/invoices/` | Customer's own invoices |

Module guides: [ACCOUNTS_PRODUCTS.md](ACCOUNTS_PRODUCTS.md) (M2) and
[SUBSCRIPTIONS.md](SUBSCRIPTIONS.md) (M1: lifecycle rules, full API, and open
integration issues).

## Roles

| Role | Access |
|------|--------|
| `admin` | Everything |
| `staff` | Dashboard, products, subscriptions, billing |
| `customer` | Portal only (own records) |


## Project Information

**Project Name:** Brightloop – Subscription Management System

**Event:** Make-A-Ton 9.0

**Organized By:** CUSAT and Odoo

**Project Type:** Web Application

**Development Approach:** Collaborative Team Development

*Built as part of Make-A-Ton 9.0.*

