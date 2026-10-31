"""
subscriptions/services.py
All subscription business rules. API views, portal pages and the
close_expired_subscriptions command call these functions; none of them
re-implement a rule.

Lifecycle:
    Draft → Quotation → Confirmed → Active ⇄ Paused
    Active/Closed → (renew) → Active
    any open status → Closed
    Quotation → Draft when the quotation expires

Every successful status change writes one SubscriptionStatusChange row in
the same transaction as the status update.
"""

from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.functions import Cast, Substr
from django.utils import timezone

from products.models import validate_plan_available

from .models import Subscription, SubscriptionLine, SubscriptionStatusChange

Status = Subscription.Status

NUMBER_PREFIX = "SUB-"
DEFAULT_QUOTE_VALIDITY_DAYS = getattr(settings, "SUBSCRIPTION_QUOTE_VALIDITY_DAYS", 30)

# Statuses a subscription can be closed from
OPEN_STATUSES = (Status.DRAFT, Status.QUOTATION, Status.CONFIRMED, Status.ACTIVE, Status.PAUSED)

BILLING_PERIOD_DELTA = {
    "daily": relativedelta(days=1),
    "weekly": relativedelta(weeks=1),
    "monthly": relativedelta(months=1),
    "yearly": relativedelta(years=1),
}


class SubscriptionError(ValueError):
    """A business rule blocked the action. `field` names the input at fault, if any."""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


# ─── Numbering ────────────────────────────────────────────────────────────────

def generate_subscription_number():
    """Next SUB-0001 style number. Uniqueness is guaranteed by the DB constraint;
    create_subscription retries if two requests pick the same number."""
    last = (
        Subscription.objects.filter(number__regex=rf"^{NUMBER_PREFIX}[0-9]+$")
        .annotate(seq=Cast(Substr("number", len(NUMBER_PREFIX) + 1), models.BigIntegerField()))
        .aggregate(m=models.Max("seq"))["m"]
    )
    return f"{NUMBER_PREFIX}{(last or 0) + 1:04d}"


def _save_with_number(subscription, attempts=5):
    for attempt in range(attempts):
        subscription.number = generate_subscription_number()
        try:
            with transaction.atomic():
                subscription.save()
            return subscription
        except IntegrityError:
            if attempt == attempts - 1:
                raise
    return subscription


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _today():
    return timezone.localdate()


def _is_customer(user):
    return bool(user and getattr(user, "role", None) == "customer")


def _staff_only(actor, action):
    if _is_customer(actor):
        raise SubscriptionError(f"Only staff can {action}.")


def _check_owner(subscription, actor):
    """Customers may only act on their own subscriptions."""
    if _is_customer(actor) and subscription.customer_id != actor.pk:
        raise SubscriptionError("You can only manage your own subscriptions.")


def _record(subscription, from_status, to_status, actor, reason=""):
    return SubscriptionStatusChange.objects.create(
        subscription=subscription,
        from_status=from_status,
        to_status=to_status,
        changed_by=actor if getattr(actor, "pk", None) else None,
        reason=reason[:255],
    )


def _lock(subscription):
    return Subscription.objects.select_for_update().select_related("plan").get(pk=subscription.pk)


def _set_status(locked, to_status, actor, reason="", **fields):
    """Update status (plus any extra fields) and write the history row. Call inside atomic()."""
    from_status = locked.status
    locked.status = to_status
    for name, value in fields.items():
        setattr(locked, name, value)
    locked.save(update_fields=["status", "updated_at", *fields.keys()])
    _record(locked, from_status, to_status, actor, reason)


def _sync(subscription):
    """Copy the saved state back onto the caller's instance."""
    subscription.refresh_from_db()
    return subscription


def _require_status(subscription, allowed, action):
    if subscription.status not in allowed:
        raise SubscriptionError(
            f"Can't {action} a subscription that is {subscription.get_status_display().lower()}."
        )


def _require_lines(subscription):
    if not subscription.lines.exists():
        raise SubscriptionError("Add at least one product line first.", field="lines")


def _validate_quantities(plan, lines):
    for line in lines:
        if line["quantity"] < plan.min_quantity:
            raise SubscriptionError(
                f"{plan.name} needs a quantity of at least {plan.min_quantity}.", field="lines",
            )


def _default_price(plan, product, variant):
    """Plan price when the line is the plan's own product, otherwise the product's sales price;
    plus the variant's extra price."""
    base = plan.price if plan.product_id and plan.product_id == product.pk else product.sales_price
    extra = variant.extra_price if variant else Decimal("0.00")
    return base + extra


def _clean_lines(plan, lines):
    """Validate line dicts ({product, variant?, quantity, unit_price?, tax_rule?}) and fill defaults."""
    if not lines:
        raise SubscriptionError("Add at least one product line.", field="lines")
    cleaned = []
    for line in lines:
        product = line["product"]
        variant = line.get("variant")
        if variant and variant.product_id != product.pk:
            raise SubscriptionError(f"Variant {variant} doesn't belong to {product}.", field="lines")
        unit_price = line.get("unit_price")
        cleaned.append({
            "product": product,
            "variant": variant,
            "quantity": int(line.get("quantity") or 1),
            "unit_price": _default_price(plan, product, variant) if unit_price is None else unit_price,
            "tax_rule": line.get("tax_rule") or product.tax_rule,
        })
    _validate_quantities(plan, cleaned)
    return cleaned


def _write_lines(subscription, cleaned_lines):
    SubscriptionLine.objects.bulk_create([
        SubscriptionLine(subscription=subscription, plan=subscription.plan, **line) for line in cleaned_lines
    ])


def _check_dates(plan, start_date, expiry_date):
    try:
        validate_plan_available(plan, start_date)
    except ValidationError as exc:
        raise SubscriptionError(exc.messages[0], field="plan")
    if expiry_date and expiry_date < start_date:
        raise SubscriptionError("Expiry date can't be before the start date.", field="expiry_date")


def _renewal_expiry(subscription, base):
    """New expiry after renewing from `base`: same term length as the original."""
    term = relativedelta(subscription.expiry_date + timedelta(days=1), subscription.start_date)
    if not term:
        term = BILLING_PERIOD_DELTA.get(subscription.plan.billing_period, relativedelta(months=1))
    return base + term - timedelta(days=1)


# ─── Create / edit ────────────────────────────────────────────────────────────

def create_subscription(*, customer, plan, start_date, lines, actor=None, expiry_date=None,
                        payment_terms=Subscription.PaymentTerms.IMMEDIATE, notes="", template=None):
    """Create a Draft subscription with its lines and the first history row."""
    if getattr(customer, "role", None) != "customer":
        raise SubscriptionError("Subscriptions can only be created for customers.", field="customer")
    if plan is None:
        raise SubscriptionError("Choose a plan.", field="plan")
    _check_dates(plan, start_date, expiry_date)
    cleaned = _clean_lines(plan, lines)

    with transaction.atomic():
        subscription = Subscription(
            customer=customer, plan=plan, template=template, start_date=start_date,
            expiry_date=expiry_date, payment_terms=payment_terms, notes=notes,
            created_by=actor if getattr(actor, "pk", None) else None,
        )
        _save_with_number(subscription)
        _write_lines(subscription, cleaned)
        _record(subscription, "", Status.DRAFT, actor, "Created")
    return subscription


def update_draft(subscription, *, actor=None, lines=None, **fields):
    """Edit a Draft. `lines`, when given, replaces all existing lines."""
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, (Status.DRAFT,), "edit")
        for name, value in fields.items():
            setattr(locked, name, value)
        _check_dates(locked.plan, locked.start_date, locked.expiry_date)
        if lines is not None:
            cleaned = _clean_lines(locked.plan, lines)
            locked.save()
            locked.lines.all().delete()
            _write_lines(locked, cleaned)
        else:
            _validate_quantities(locked.plan, locked.lines.values("quantity"))
            locked.save()
            # Keep line.plan in step with a changed subscription.plan
            locked.lines.update(plan=locked.plan)
    return _sync(subscription)


def create_from_template(template, *, customer, start_date, actor=None):
    """Copy the template's plan, terms and lines into a new, independent Draft."""
    if not template.is_active:
        raise SubscriptionError("This template is archived.", field="template")
    lines = [
        {"product": t.product, "variant": t.variant, "quantity": t.quantity, "unit_price": t.unit_price}
        for t in template.lines.select_related("product__tax_rule", "variant")
    ]
    expiry_date = None
    if template.duration_months:
        expiry_date = start_date + relativedelta(months=template.duration_months) - timedelta(days=1)
    return create_subscription(
        customer=customer, plan=template.plan, start_date=start_date, lines=lines, actor=actor,
        expiry_date=expiry_date, payment_terms=template.payment_terms, notes=template.notes,
        template=template,
    )


# ─── Status transitions ───────────────────────────────────────────────────────

def send_quote(subscription, actor=None, validity_days=None):
    """Draft → Quotation, with a quotation expiry date."""
    _staff_only(actor, "send quotes")
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, (Status.DRAFT,), "send a quote for")
        _require_lines(locked)
        _validate_quantities(locked.plan, locked.lines.values("quantity"))
        if validity_days is None:
            validity_days = locked.template.validity_days if locked.template_id else DEFAULT_QUOTE_VALIDITY_DAYS
        if validity_days < 1:
            raise SubscriptionError("Validity must be at least 1 day.", field="validity_days")
        expiry = _today() + timedelta(days=validity_days)
        _set_status(locked, Status.QUOTATION, actor, f"Quote sent, valid until {expiry}",
                    quotation_expiry=expiry)
    return _sync(subscription)


def expire_quotation(subscription):
    """Quotation → Draft if its expiry date has passed. Returns True if it expired."""
    with transaction.atomic():
        locked = _lock(subscription)
        if not (locked.status == Status.QUOTATION and locked.quotation_expiry
                and locked.quotation_expiry < _today()):
            return False
        _set_status(locked, Status.DRAFT, None, f"Quotation expired on {locked.quotation_expiry}")
    _sync(subscription)
    return True


def expire_quotations(queryset=None):
    """Revert every expired quotation (optionally within `queryset`). Returns how many."""
    queryset = Subscription.objects.all() if queryset is None else queryset
    due = queryset.filter(status=Status.QUOTATION, quotation_expiry__lt=_today())
    return sum(1 for sub in due if expire_quotation(sub))


def confirm_subscription(subscription, actor=None):
    """Quotation → Confirmed. An expired quotation goes back to Draft instead."""
    _check_owner(subscription, actor)
    if expire_quotation(subscription):
        raise SubscriptionError(
            f"This quotation expired on {subscription.quotation_expiry}. Send a new quote."
        )
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, (Status.QUOTATION,), "confirm")
        _set_status(locked, Status.CONFIRMED, actor, "Quotation confirmed")
    return _sync(subscription)


def activate_subscription(subscription, actor=None):
    """Confirmed → Active. Billing starts on the start date."""
    _staff_only(actor, "activate subscriptions")
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, (Status.CONFIRMED,), "activate")
        _require_lines(locked)
        if locked.expiry_date and locked.expiry_date < _today():
            raise SubscriptionError("This subscription's expiry date has already passed.")
        _set_status(locked, Status.ACTIVE, actor, "Activated",
                    next_billing_date=locked.next_billing_date or locked.start_date)
    return _sync(subscription)


def pause_subscription(subscription, actor=None, reason=""):
    """Active → Paused, only when the plan allows pausing."""
    _check_owner(subscription, actor)
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, (Status.ACTIVE,), "pause")
        if not locked.plan or not locked.plan.pausable:
            raise SubscriptionError("This plan doesn't allow pausing.")
        _set_status(locked, Status.PAUSED, actor, reason or "Paused")
    return _sync(subscription)


def resume_subscription(subscription, actor=None, reason=""):
    """Paused → Active, unless the subscription has expired meanwhile."""
    _check_owner(subscription, actor)
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, (Status.PAUSED,), "resume")
        if locked.expiry_date and locked.expiry_date < _today():
            raise SubscriptionError("This subscription has expired. Renew it instead.")
        _set_status(locked, Status.ACTIVE, actor, reason or "Resumed")
    return _sync(subscription)


def renew_subscription(subscription, actor=None):
    """Extend the term by its original length. Allowed from Active or Closed when the plan is renewable."""
    _check_owner(subscription, actor)
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, (Status.ACTIVE, Status.CLOSED), "renew")
        if not locked.plan or not locked.plan.renewable:
            raise SubscriptionError("This plan doesn't allow renewal.")
        if not locked.expiry_date:
            raise SubscriptionError("This subscription has no expiry date, so it doesn't need renewing.")
        base = max(locked.expiry_date + timedelta(days=1), _today())
        new_expiry = _renewal_expiry(locked, base)
        fields = {"expiry_date": new_expiry}
        if locked.status == Status.CLOSED:
            fields["next_billing_date"] = base
        _set_status(locked, Status.ACTIVE, actor, f"Renewed until {new_expiry}", **fields)
    return _sync(subscription)


def close_subscription(subscription, actor=None, reason=""):
    """Close an open subscription. Before expiry, an Active/Paused one needs a closable plan."""
    _check_owner(subscription, actor)
    with transaction.atomic():
        locked = _lock(subscription)
        _require_status(locked, OPEN_STATUSES, "close")
        expired = locked.expiry_date is not None and locked.expiry_date < _today()
        running = locked.status in (Status.ACTIVE, Status.PAUSED)
        if running and not expired and not (locked.plan and locked.plan.closable):
            raise SubscriptionError("This plan doesn't allow closing before the expiry date.")
        _set_status(locked, Status.CLOSED, actor, reason or "Closed", next_billing_date=None)
    return _sync(subscription)


def close_expired_subscriptions(today=None):
    """Close Active/Paused subscriptions past their expiry date whose plan has auto_close.
    Returns the closed subscriptions' numbers."""
    today = today or _today()
    due = Subscription.objects.filter(
        status__in=(Status.ACTIVE, Status.PAUSED), expiry_date__lt=today, plan__auto_close=True,
    ).order_by("id")
    closed = []
    for sub in due:
        with transaction.atomic():
            locked = _lock(sub)
            if locked.status not in (Status.ACTIVE, Status.PAUSED):
                continue   # changed since the query ran
            _set_status(locked, Status.CLOSED, None, f"Expired on {locked.expiry_date} (auto-close)",
                        next_billing_date=None)
        closed.append(locked.number)
    return closed
