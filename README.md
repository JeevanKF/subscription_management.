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


## Project Information

**Project Name:** Brightloop – Subscription Management System

**Event:** Make-A-Ton 9.0

**Organized By:** CUSAT and Odoo

**Project Type:** Web Application

**Development Approach:** Collaborative Team Development

*Built as part of Make-A-Ton 9.0.*

