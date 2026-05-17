"""Stripe webhook event handlers.

Idempotency model: every event is recorded in `payment_events` with a unique
`event_id`. If we see the same event twice we short-circuit immediately.

Events we care about:
- `checkout.session.completed`     -> activate / extend Subscription
- `invoice.paid`                   -> push expires_at forward (for renewals)
- `invoice.payment_failed`         -> log + leave status untouched
- `customer.subscription.updated`  -> sync expires_at / status
- `customer.subscription.deleted`  -> mark canceled
- `charge.refunded`                -> mark refunded

All handlers are pure and synchronous so the webhook returns within the
3-second Stripe deadline.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.alert import notify_admin
from app.core.email_templates import (
    paid_confirmation,
    payment_failed as payment_failed_email,
    referral_bonus,
)
from app.core.locale import stored_or
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.core.referral import grant_first_paid_bonus
from app.models.payment_event import PaymentEvent
from app.models.subscription import Subscription
from app.models.user import User


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ts_to_dt(ts: int | float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def _record_event(
    db: Session,
    event: dict[str, Any],
    *,
    user_id: int | None = None,
    subscription_id: int | None = None,
) -> bool:
    """Insert into payment_events. Returns True iff this is a new event."""
    event_id = event.get("id")
    if not event_id:
        logger.warning("webhook: event without id, ignoring")
        return False
    existing = db.scalar(
        select(PaymentEvent).where(PaymentEvent.event_id == event_id)
    )
    if existing is not None:
        return False
    db.add(
        PaymentEvent(
            event_id=event_id,
            type=event.get("type", ""),
            user_id=user_id,
            subscription_id=subscription_id,
            payload=event.get("data", {}).get("object"),
            received_at=_now(),
        )
    )
    return True


def _user_for_session(db: Session, sess: dict[str, Any]) -> User | None:
    """Find the local user from a Checkout Session payload."""
    crid = sess.get("client_reference_id")
    if crid:
        try:
            return db.get(User, int(crid))
        except (ValueError, TypeError):
            pass
    cust = sess.get("customer")
    if cust:
        return db.scalar(select(User).where(User.stripe_customer_id == str(cust)))
    return None


def _user_for_customer(db: Session, customer_id: str | None) -> User | None:
    if not customer_id:
        return None
    return db.scalar(select(User).where(User.stripe_customer_id == customer_id))


# ---------- handlers ----------

def _handle_checkout_completed(db: Session, obj: dict[str, Any]) -> int | None:
    """Activate a subscription on `checkout.session.completed`."""
    user = _user_for_session(db, obj)
    if user is None:
        logger.warning("webhook: checkout.session.completed but user not found")
        return None

    metadata = obj.get("metadata") or {}
    plan = metadata.get("plan")
    if not plan:
        logger.warning("webhook: missing plan in metadata, session={}", obj.get("id"))
        return None

    brief_id = metadata.get("brief_id")
    brief_id_int = int(brief_id) if brief_id else None
    session_id = obj.get("id")
    sub_id_stripe = obj.get("subscription")
    amount = obj.get("amount_total")
    currency = obj.get("currency")

    # Idempotency on the local row: if we already saw this session, no-op.
    existing = db.scalar(
        select(Subscription).where(Subscription.stripe_session_id == session_id)
    )
    if existing is not None:
        logger.info("webhook: subscription already exists for session {}", session_id)
        return existing.id

    sub = Subscription(
        user_id=user.id,
        plan=plan,
        status="active",
        provider="stripe",
        provider_ref=sub_id_stripe or session_id,
        stripe_session_id=session_id,
        stripe_subscription_id=sub_id_stripe,
        brief_id=brief_id_int,
        amount_cents=amount,
        currency=currency,
        started_at=_now(),
        expires_at=None,  # populated by invoice.paid / subscription.updated
    )
    db.add(sub)
    db.flush()
    logger.info(
        "webhook: subscription activated user={} plan={} sub_id={} session={}",
        user.id, plan, sub.id, session_id,
    )

    # D13: send paid-confirmation email + grant referral bonus on first paid sub.
    _post_first_paid(db, user, sub)
    # D19: real-time admin alert.
    amount_str = ""
    if amount and currency:
        amount_str = f"{amount/100:.2f} {currency.upper()}"
    notify_admin(
        f"💸 New paid subscription · {plan}",
        f"User {user.email} (#{user.id}) just activated {plan}. {amount_str}".strip(),
        level="success",
        key=None,  # never throttle revenue events
    )
    return sub.id


def _post_first_paid(db: Session, user: User, sub: Subscription) -> None:
    """Side-effects after a successful first paid checkout. Best-effort:
    failures are logged but never break the webhook response."""
    # Was this the user's first paid subscription? (i.e. only this row exists)
    earlier = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .where(Subscription.id != sub.id)
        .where(Subscription.provider == "stripe")
        .limit(1)
    )
    is_first_paid = earlier is None

    if smtp_enabled():
        try:
            subj, txt, html = paid_confirmation(
                user.email,
                plan=sub.plan,
                amount_cents=sub.amount_cents,
                currency=sub.currency,
                brief_id=sub.brief_id,
                locale=stored_or("en", user.locale),
            )
            send_email(to=user.email, subject=subj, text=txt, html=html)
        except Exception as exc:  # noqa: BLE001
            logger.warning("paid confirmation email failed: {}", exc)

    if not is_first_paid:
        return

    grant = grant_first_paid_bonus(db, user)
    if grant is None:
        return
    referrer = db.get(User, grant.referrer_user_id)
    if referrer is None or not smtp_enabled():
        return
    try:
        subj, txt, html = referral_bonus(
            referrer.email,
            referred_email=user.email,
            bonus_days=grant.bonus_days,
            locale=stored_or("en", referrer.locale),
        )
        send_email(to=referrer.email, subject=subj, text=txt, html=html)
    except Exception as exc:  # noqa: BLE001
        logger.warning("referral bonus email failed: {}", exc)


def _handle_invoice_paid(db: Session, obj: dict[str, Any]) -> int | None:
    """Roll the local sub's expires_at forward when an invoice is paid."""
    sub_stripe_id = obj.get("subscription")
    if not sub_stripe_id:
        return None
    sub = db.scalar(
        select(Subscription).where(
            Subscription.stripe_subscription_id == sub_stripe_id
        )
    )
    if sub is None:
        return None
    period_end = obj.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
    if not period_end:
        period_end = obj.get("period_end")
    sub.expires_at = _ts_to_dt(period_end)
    sub.status = "active"
    return sub.id


def _handle_invoice_failed(db: Session, obj: dict[str, Any]) -> int | None:
    """`invoice.payment_failed`: notify the user + raise an admin alert.

    Stripe's smart retries will continue attempting on its own schedule; we
    don't change `Subscription.status` here (the eventual `subscription.updated`
    event will mark it past_due/canceled if it never recovers)."""
    sub_stripe_id = obj.get("subscription")
    sub: Subscription | None = None
    if sub_stripe_id:
        sub = db.scalar(
            select(Subscription).where(
                Subscription.stripe_subscription_id == sub_stripe_id
            )
        )

    user: User | None = None
    if sub is not None:
        user = db.get(User, sub.user_id)
    else:
        user = _user_for_customer(db, obj.get("customer"))

    plan = sub.plan if sub else (obj.get("lines", {}).get("data", [{}])[0]
                                 .get("plan", {}).get("nickname") or "subscription")

    if user is not None and smtp_enabled():
        try:
            subj, txt, html = payment_failed_email(
                user.email, plan=plan, locale=stored_or("en", user.locale)
            )
            send_email(to=user.email, subject=subj, text=txt, html=html)
        except Exception as exc:  # noqa: BLE001
            logger.warning("payment_failed email failed: {}", exc)

    notify_admin(
        f"⚠️ Payment failed · {plan}",
        f"Stripe declined the renewal charge for "
        f"{user.email if user else 'unknown user'}"
        f" (sub={sub.id if sub else '?'}). Stripe will retry per smart retries.",
        level="warn",
        key=f"payment_failed:{sub.id if sub else 'unknown'}",
    )
    return sub.id if sub else None


def _handle_subscription_updated(db: Session, obj: dict[str, Any]) -> int | None:
    sub = db.scalar(
        select(Subscription).where(
            Subscription.stripe_subscription_id == obj.get("id")
        )
    )
    if sub is None:
        return None
    status = obj.get("status", "active")
    # Stripe statuses: active, trialing, past_due, canceled, unpaid, incomplete...
    if status in ("active", "trialing"):
        sub.status = "active"
    elif status in ("canceled", "unpaid", "incomplete_expired"):
        sub.status = "canceled"
    else:
        sub.status = status
    sub.expires_at = _ts_to_dt(obj.get("current_period_end"))
    return sub.id


def _handle_subscription_deleted(db: Session, obj: dict[str, Any]) -> int | None:
    sub = db.scalar(
        select(Subscription).where(
            Subscription.stripe_subscription_id == obj.get("id")
        )
    )
    if sub is None:
        return None
    sub.status = "canceled"
    sub.expires_at = _ts_to_dt(obj.get("ended_at")) or _now()
    return sub.id


def _handle_charge_refunded(db: Session, obj: dict[str, Any]) -> int | None:
    """`charge.refunded` carries a payment_intent we recorded against the session."""
    pi = obj.get("payment_intent")
    if not pi:
        return None
    sub = db.scalar(
        select(Subscription).where(Subscription.provider_ref == pi)
    )
    if sub is None:
        # Fall back: try matching via session->payment_intent expansion. We
        # don't fetch from Stripe here to keep webhook fast.
        return None
    sub.status = "refunded"
    return sub.id


_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_succeeded": _handle_invoice_paid,
    "invoice.payment_failed": _handle_invoice_failed,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "charge.refunded": _handle_charge_refunded,
}


def handle_event(db: Session, event: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a verified Stripe event. Idempotent on event_id.

    Returns a small status dict useful for tests / logs.
    """
    event_id = event.get("id", "")
    etype = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}

    fresh = _record_event(db, event)
    if not fresh:
        db.commit()
        logger.info("webhook: duplicate event {} ({}), no-op", event_id, etype)
        return {"status": "duplicate", "event_id": event_id}

    handler = _HANDLERS.get(etype)
    sub_id: int | None = None
    if handler is not None:
        try:
            sub_id = handler(db, obj)
        except Exception as exc:  # noqa: BLE001
            logger.exception("webhook handler {} crashed: {}", etype, exc)
            db.rollback()
            # Re-record the event so we don't loop, but mark with type+_failed
            db.add(
                PaymentEvent(
                    event_id=event_id,
                    type=f"{etype}__failed",
                    payload={"error": str(exc)},
                    received_at=_now(),
                )
            )
            db.commit()
            return {"status": "error", "event_id": event_id, "error": str(exc)}

    # Backfill the subscription_id on the event row so admin queries are easy.
    if sub_id is not None:
        evt = db.scalar(
            select(PaymentEvent).where(PaymentEvent.event_id == event_id)
        )
        if evt is not None:
            evt.subscription_id = sub_id

    db.commit()
    return {
        "status": "ok",
        "event_id": event_id,
        "type": etype,
        "subscription_id": sub_id,
        "handled": handler is not None,
    }


__all__ = ["handle_event"]
