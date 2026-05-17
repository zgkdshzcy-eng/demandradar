"""Stripe integration: thin, side-effect-free wrapper.

All callers go through `client()` which returns the configured `stripe`
module (or raises `PaymentsDisabled` when no STRIPE_SECRET_KEY is set), and
through `plan_to_price_id()` which validates a plan name against the
configured price catalogue.

We deliberately import the `stripe` package lazily so dev/test environments
without the dependency installed (or without keys configured) still work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.logging import logger


class PaymentsDisabled(RuntimeError):
    """Raised when an endpoint requires Stripe but it isn't configured."""


# ---------- catalogue ----------

@dataclass(frozen=True)
class PlanSpec:
    plan: str
    mode: str  # "subscription" | "payment"
    needs_brief_id: bool = False


PLANS: dict[str, PlanSpec] = {
    "weekly_pro": PlanSpec("weekly_pro", "subscription"),
    "studio": PlanSpec("studio", "subscription"),
    "brief_oneoff": PlanSpec("brief_oneoff", "payment", needs_brief_id=True),
}


def plan_to_price_id(plan: str) -> str:
    """Return the configured Stripe Price ID for a plan name. Raises ValueError
    on unknown plan or when the env var is missing."""
    if plan == "weekly_pro":
        pid = settings.stripe_price_weekly_pro
    elif plan == "studio":
        pid = settings.stripe_price_studio
    elif plan == "brief_oneoff":
        pid = settings.stripe_price_brief_oneoff
    else:
        raise ValueError(f"unknown plan: {plan}")
    if not pid:
        raise ValueError(f"price id for plan '{plan}' not configured")
    return pid


# ---------- client ----------

_initialised = False


def client():  # type: ignore[no-untyped-def]
    """Return the configured `stripe` module. Raises PaymentsDisabled when
    no API key is set."""
    global _initialised
    if not settings.stripe_secret_key:
        raise PaymentsDisabled("STRIPE_SECRET_KEY is not configured")
    import stripe  # local import: keeps the dep optional at import time

    if not _initialised:
        stripe.api_key = settings.stripe_secret_key
        # Pin to a known API version so behaviour doesn't drift under us.
        stripe.api_version = "2024-09-30.acacia"
        _initialised = True
        logger.info("stripe client initialised version={}", stripe.api_version)
    return stripe


def is_enabled() -> bool:
    return bool(settings.stripe_secret_key)


# ---------- helpers ----------

def verify_webhook(payload: bytes, signature: str) -> dict[str, Any]:
    """Verify a Stripe webhook payload and return the parsed event.

    Raises ValueError on signature mismatch / missing secret.
    """
    if not settings.stripe_webhook_secret:
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")
    stripe = client()
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:  # type: ignore[attr-defined]
        raise ValueError(f"signature verification failed: {e}") from e
    # `event` is a StripeObject; coerce to plain dict for storage.
    return dict(event)


def ensure_customer(user) -> str:  # type: ignore[no-untyped-def]
    """Return the Stripe customer id for a user, creating one if needed.
    The caller is responsible for committing the user row afterwards.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id
    stripe = client()
    customer = stripe.Customer.create(
        email=user.email,
        name=user.name or None,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer["id"]
    return customer["id"]


def create_checkout_session(
    user,  # type: ignore[no-untyped-def]
    *,
    plan: str,
    success_url: str,
    cancel_url: str,
    brief_id: int | None = None,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for a plan.

    Returns the session as a plain dict so callers don't depend on stripe
    response objects.
    """
    spec = PLANS.get(plan)
    if spec is None:
        raise ValueError(f"unknown plan: {plan}")
    if spec.needs_brief_id and brief_id is None:
        raise ValueError("brief_id is required for brief_oneoff")

    price_id = plan_to_price_id(plan)
    customer_id = ensure_customer(user)
    stripe = client()

    metadata: dict[str, str] = {
        "user_id": str(user.id),
        "plan": plan,
    }
    if brief_id is not None:
        metadata["brief_id"] = str(brief_id)

    session = stripe.checkout.Session.create(
        mode=spec.mode,
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(user.id),
        metadata=metadata,
        # For subscription mode propagate metadata onto the Subscription too,
        # so we can recover the plan when handling subscription.* webhooks.
        subscription_data={"metadata": metadata} if spec.mode == "subscription" else None,
        payment_intent_data=(
            {"metadata": metadata} if spec.mode == "payment" else None
        ),
        allow_promotion_codes=True,
    )
    return dict(session)


def create_billing_portal_session(user, return_url: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Open a Stripe Customer Portal session for the given user."""
    if not user.stripe_customer_id:
        raise ValueError("user has no stripe_customer_id")
    stripe = client()
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=return_url,
    )
    return dict(session)


def refund_subscription(sub) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Refund the most recent charge for a subscription, then cancel it.

    Returns a small dict describing the action. Caller updates the local
    Subscription row.
    """
    stripe = client()
    out: dict[str, Any] = {"refunded": False, "canceled": False, "details": {}}

    if sub.stripe_subscription_id:
        # Recurring sub: cancel at Stripe; final refund (if any) handled manually.
        canceled = stripe.Subscription.delete(sub.stripe_subscription_id)
        out["canceled"] = True
        out["details"]["subscription"] = {"status": canceled.get("status")}

    # One-time payment_intent path: pull the most recent charge from the session.
    if sub.stripe_session_id:
        sess = stripe.checkout.Session.retrieve(
            sub.stripe_session_id, expand=["payment_intent"]
        )
        pi = sess.get("payment_intent")
        pi_id = pi["id"] if isinstance(pi, dict) else pi
        if pi_id:
            refund = stripe.Refund.create(payment_intent=pi_id)
            out["refunded"] = True
            out["details"]["refund"] = {"id": refund["id"], "status": refund["status"]}
    return out


__all__ = [
    "PLANS",
    "PaymentsDisabled",
    "client",
    "create_billing_portal_session",
    "create_checkout_session",
    "ensure_customer",
    "is_enabled",
    "plan_to_price_id",
    "refund_subscription",
    "verify_webhook",
]
