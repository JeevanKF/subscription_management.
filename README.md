# Brightloop SMS

> Subscription management system — Django REST API + React (Vite) frontend.

## Project structure

```
brightloop/
├── config/          # Django project (settings, urls, wsgi)
├── accounts/        # Custom User model + Token auth API
├── products/        # Product, Variant, Plan, TaxRule
├── subscriptions/   # Subscription, SubscriptionLine
├── billing/         # Invoice, InvoiceLine, Payment, Discount
├── dashboard/       # Finance metrics API (admin/staff)
├── portal/          # Customer self-service API
├── frontend/        # React (Vite) SPA
│   └── src/
│       ├── api/         # Axios API modules per app
│       ├── context/     # AuthContext (token + user)
│       ├── components/  # Navbar, ProtectedRoute
│       └── pages/       # One page component per route
├── .env             # Local secrets — never commit
├── .env.example     # Template
└── requirements.txt
```

## Local setup

### 1. Backend

```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# Copy env file and fill in your PostgreSQL credentials
copy .env.example .env

# Create the database in PostgreSQL first:
#   CREATE DATABASE brightloop;

python manage.py migrate
python manage.py createsuperuser   # create the first admin
python manage.py runserver         # runs on http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev    # runs on http://localhost:5173
```

Vite proxies all `/api/*` requests to Django on port 8000 — no CORS issues in dev.

## API endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/auth/health/` | PostgreSQL health check (public) |
| POST | `/api/auth/login/` | Get auth token |
| POST | `/api/auth/logout/` | Delete token |
| GET | `/api/auth/me/` | Current user profile |
| GET | `/api/products/` | Product list |
| GET/POST | `/api/subscriptions/` | Subscription list / create |
| GET/POST | `/api/billing/invoices/` | Invoice list |
| GET | `/api/dashboard/` | Finance summary (admin/staff) |
| GET | `/api/portal/subscriptions/` | Customer's own subscriptions |
| GET | `/api/portal/invoices/` | Customer's own invoices |

## Roles

| Role | Access |
|------|--------|
| `admin` | Everything |
| `staff` | Dashboard, products, subscriptions, billing |
| `customer` | Portal only (own records) |

