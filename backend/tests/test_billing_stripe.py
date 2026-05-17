"""D12 Stripe integration tests.

We don't talk to Stripe at all here. Instead we monkeypatch:
- `app.core.payments.is_enabled` / `client` / `verify_webhook` etc.
- and feed crafted webhook payloads through the real `handle_event` pipeline.

This validates: webhook idempotency, plan-aware Subscription creation, the
brief_oneoff -> entitlement.unlocked_brief_ids round-trip, refund semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.billing.webhook import handle_event
from app.core.entitlement import compute_entitlement
from app.core.security import issue_magic_link_token
from app.db.session import SessionLocal
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.payment_event import PaymentEvent
from app.models.subscription import Subscription
from app.models.user import User


# ---------------- helpers ----------------

def _login(client: TestClient, email: str) -> dict[str, str]:
    token = issue_magic_link_token(email)
    r = client.post("/api/auth/exchange", json={"token": token})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user(email: str) -> User:
    with SessionLocal() as db:
        return db.scalar(select(User).where(User.email == email))  # type: ignore[return-value]


def _make_brief() -> int:
    with SessionLocal() as db:
        pp = PainPoint(pain="stripe-test", target_user="x")
        db.add(pp)
        db.flush()
        b = Brief(
            pain_point_id=pp.id,
            title="Stripe Test Brief",
            markdown="# Locked\n\nSecret",
            visibility="paid",
            version=1,
        )
        db.add(b)
        db.commit()
        return b.id


def _checkout_event(
    *,
    event_id: str,
    user_id: int,
    plan: str,
    session_id: str,
    sub_id: str | None = None,
    brief_id: int | None = None,
    amount_total: int = 9900,
    customer: str = "cus_TEST",
) -> dict[str, Any]:
    metadata = {"plan": plan, "user_id": str(user_id)}
    if brief_id is not None:
        metadata["brief_id"] = str(brief_id)
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "client_reference_id": str(user_id),
                "customer": customer,
                "subscription": sub_id,
                "amount_total": amount_total,
                "currency": "cny",
                "metadata": metadata,
            }
        },
    }


# ---------------- webhook business logic ----------------

def test_checkout_completed_creates_active_subscription(client: TestClient) -> None:
    _login(client, "stripe-w1@example.com")
    user = _user("stripe-w1@example.com")
    assert user is not None

    event = _checkout_event(
        event_id="evt_w1",
        user_id=user.id,
        plan="weekly_pro",
        session_id="cs_w1",
        sub_id="sub_w1",
    )
    with SessionLocal() as db:
        out = handle_event(db, event)
    assert out["status"] == "ok"
    assert out["subscription_id"] is not None

    with SessionLocal() as db:
        sub = db.scalar(
            select(Subscription).where(Subscription.stripe_session_id == "cs_w1")
        )
        assert sub is not None
        assert sub.plan == "weekly_pro"
        assert sub.provider == "stripe"
        assert sub.status == "active"
        assert sub.stripe_subscription_id == "sub_w1"
        assert sub.amount_cents == 9900
        assert sub.currency == "cny"


def test_brief_oneoff_unlocks_only_target_brief(client: TestClient) -> None:
    _login(client, "stripe-b1@example.com")
    user = _user("stripe-b1@example.com")
    bid = _make_brief()
    other_bid = _make_brief()

    event = _checkout_event(
        event_id="evt_b1",
        user_id=user.id,
        plan="brief_oneoff",
        session_id="cs_b1",
        brief_id=bid,
    )
    with SessionLocal() as db:
        handle_event(db, event)
        ent = compute_entitlement(db, db.get(User, user.id))
    assert bid in ent.unlocked_brief_ids
    assert other_bid not in ent.unlocked_brief_ids
    assert ent.can_read_any_brief is False


def test_webhook_is_idempotent_on_event_id() -> None:
    user = _user("stripe-w1@example.com")  # reuse
    event = _checkout_event(
        event_id="evt_dup",
        user_id=user.id,
        plan="weekly_pro",
        session_id="cs_dup",
    )
    with SessionLocal() as db:
        first = handle_event(db, event)
        second = handle_event(db, event)
    assert first["status"] == "ok"
    assert second["status"] == "duplicate"

    with SessionLocal() as db:
        evts = list(
            db.execute(
                select(PaymentEvent).where(PaymentEvent.event_id == "evt_dup")
            ).scalars()
        )
        assert len(evts) == 1


def test_invoice_paid_extends_expiry() -> None:
    """Once a `invoice.paid` arrives we set expires_at to the period end."""
    with SessionLocal() as db:
        sub = db.scalar(
            select(Subscription).where(Subscription.stripe_subscription_id == "sub_w1")
        )
        assert sub is not None
        assert sub.expires_at is None  # checkout.session.completed left it null

    end_ts = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp())
    event = {
        "id": "evt_inv1",
        "type": "invoice.paid",
        "data": {
            "object": {
                "subscription": "sub_w1",
                "lines": {"data": [{"period": {"end": end_ts}}]},
            }
        },
    }
    with SessionLocal() as db:
        out = handle_event(db, event)
    assert out["status"] == "ok"
    assert out["subscription_id"] is not None

    with SessionLocal() as db:
        sub = db.scalar(
            select(Subscription).where(Subscription.stripe_subscription_id == "sub_w1")
        )
        assert sub is not None
        assert sub.expires_at is not None
        assert sub.status == "active"


def test_subscription_deleted_cancels() -> None:
    event = {
        "id": "evt_del1",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_w1", "ended_at": None}},
    }
    with SessionLocal() as db:
        handle_event(db, event)
        sub = db.scalar(
            select(Subscription).where(Subscription.stripe_subscription_id == "sub_w1")
        )
    assert sub is not None
    assert sub.status == "canceled"


# ---------------- HTTP endpoints ----------------

def test_checkout_returns_redeem_only_when_stripe_disabled(client: TestClient) -> None:
    headers = _login(client, "stripe-disabled@example.com")
    r = client.post(
        "/api/billing/checkout",
        headers=headers,
        json={"plan": "weekly_pro"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "redeem_only"
    assert body["url"] is None


def test_checkout_calls_stripe_when_enabled(monkeypatch, client: TestClient) -> None:  # type: ignore[no-untyped-def]
    from app.core import config as cfg
    from app.core import payments as pay

    monkeypatch.setattr(cfg.settings, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(
        cfg.settings, "stripe_price_weekly_pro", "price_weekly_pro_test", raising=False
    )

    captured: dict[str, Any] = {}

    def fake_create_checkout_session(user, **kwargs):  # type: ignore[no-untyped-def]
        captured["user_id"] = user.id
        captured["kwargs"] = kwargs
        # Also exercise ensure_customer path: write the customer id like Stripe would.
        user.stripe_customer_id = "cus_TEST"
        return {"id": "cs_TEST", "url": "https://checkout.stripe.com/test"}

    monkeypatch.setattr(pay, "create_checkout_session", fake_create_checkout_session)

    headers = _login(client, "stripe-on@example.com")
    r = client.post(
        "/api/billing/checkout",
        headers=headers,
        json={"plan": "weekly_pro"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "stripe"
    assert body["url"] == "https://checkout.stripe.com/test"
    assert body["session_id"] == "cs_TEST"
    assert captured["kwargs"]["plan"] == "weekly_pro"
    assert "success_url" in captured["kwargs"]


def test_webhook_endpoint_rejects_missing_signature(client: TestClient) -> None:
    r = client.post("/api/billing/webhook/stripe", content=b"{}")
    assert r.status_code == 400


def test_webhook_endpoint_dispatches_to_handle_event(
    monkeypatch, client: TestClient
) -> None:  # type: ignore[no-untyped-def]
    """End-to-end: bypass signature verify, ensure handle_event runs."""
    from app.core import config as cfg
    from app.core import payments as pay

    monkeypatch.setattr(cfg.settings, "stripe_secret_key", "sk_test_x", raising=False)
    monkeypatch.setattr(
        cfg.settings, "stripe_webhook_secret", "whsec_test_x", raising=False
    )

    user = _user("stripe-w1@example.com")
    event = _checkout_event(
        event_id="evt_http1",
        user_id=user.id,
        plan="weekly_pro",
        session_id="cs_http1",
        sub_id="sub_http1",
    )
    monkeypatch.setattr(pay, "verify_webhook", lambda body, sig: event)

    r = client.post(
        "/api/billing/webhook/stripe",
        content=b"{}",
        headers={"stripe-signature": "t=1,v1=fake"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["type"] == "checkout.session.completed"


def test_admin_refund_requires_admin(client: TestClient) -> None:
    headers = _login(client, "stripe-norefund@example.com")
    r = client.post("/api/billing/refund/1", headers=headers)
    assert r.status_code == 403


def test_admin_refund_marks_status(monkeypatch, client: TestClient) -> None:  # type: ignore[no-untyped-def]
    from app.core import config as cfg
    from app.core import payments as pay

    monkeypatch.setattr(cfg.settings, "stripe_secret_key", "sk_test_x", raising=False)

    headers = _login(client, "stripe-adm@example.com")
    user = _user("stripe-adm@example.com")
    with SessionLocal() as db:
        u = db.get(User, user.id)
        u.is_admin = True
        sub = Subscription(
            user_id=u.id,
            plan="weekly_pro",
            status="active",
            provider="stripe",
            stripe_subscription_id="sub_to_refund",
        )
        db.add(sub)
        db.commit()
        sub_id = sub.id

    monkeypatch.setattr(
        pay,
        "refund_subscription",
        lambda sub: {"refunded": False, "canceled": True, "details": {}},
    )

    r = client.post(f"/api/billing/refund/{sub_id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["canceled"] is True

    with SessionLocal() as db:
        sub = db.get(Subscription, sub_id)
        assert sub.status == "canceled"
