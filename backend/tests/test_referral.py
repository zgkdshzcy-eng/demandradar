"""Referral logic + admin gating + email template smoke tests (D13)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.billing.webhook import handle_event
from app.core import email_templates as et
from app.core.referral import (
    BONUS_DAYS_FIRST_PAID,
    apply_referral,
    ensure_referral_code,
    grant_first_paid_bonus,
)
from app.core.security import issue_magic_link_token
from app.db import session as db_session
from app.models.referral_grant import ReferralGrant
from app.models.subscription import Subscription
from app.models.user import User


# ---------- helpers ----------

def _login(client: TestClient, email: str) -> dict[str, str]:
    token = issue_magic_link_token(email)
    r = client.post("/api/auth/exchange", json={"token": token})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _login_with_ref(client: TestClient, email: str, ref: str) -> dict[str, str]:
    token = issue_magic_link_token(email, ref=ref)
    r = client.post("/api/auth/exchange", json={"token": token})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user(email: str) -> User:
    with db_session.SessionLocal() as db:
        return db.scalar(select(User).where(User.email == email))  # type: ignore[return-value]


# ---------- referral core ----------

def test_ensure_referral_code_is_stable_and_unique() -> None:
    with db_session.SessionLocal() as db:
        u = User(email="ref-stable@example.com", is_active=True)
        db.add(u)
        db.commit()
        c1 = ensure_referral_code(db, u)
        c2 = ensure_referral_code(db, u)
        db.commit()
        assert c1 == c2
        assert 6 <= len(c1) <= 16
        assert c1.isalnum()


def test_apply_referral_links_and_is_idempotent() -> None:
    with db_session.SessionLocal() as db:
        a = User(email="ref-a@example.com", is_active=True)
        b = User(email="ref-b@example.com", is_active=True)
        db.add_all([a, b])
        db.commit()
        code = ensure_referral_code(db, a)
        db.commit()

        r1 = apply_referral(db, b, code)
        assert r1 is not None and r1.id == a.id
        assert b.referred_by_user_id == a.id

        # Re-applying with a *different* code is a no-op once already linked.
        c = User(email="ref-c@example.com", is_active=True)
        db.add(c)
        db.commit()
        c_code = ensure_referral_code(db, c)
        db.commit()
        r2 = apply_referral(db, b, c_code)
        assert r2 is None
        assert b.referred_by_user_id == a.id


def test_apply_referral_self_referral_rejected() -> None:
    with db_session.SessionLocal() as db:
        a = User(email="ref-self@example.com", is_active=True)
        db.add(a)
        db.commit()
        code = ensure_referral_code(db, a)
        db.commit()
        assert apply_referral(db, a, code) is None
        assert a.referred_by_user_id is None


def test_grant_first_paid_bonus_extends_active_sub() -> None:
    """Referrer with an active weekly_pro sub gets bonus days appended to expiry."""
    with db_session.SessionLocal() as db:
        # Seed referrer with an active sub.
        ref = User(email="ref-grant-r@example.com", is_active=True)
        db.add(ref)
        db.commit()
        code = ensure_referral_code(db, ref)
        sub = Subscription(
            user_id=ref.id,
            plan="weekly_pro",
            status="active",
            provider="stripe",
            stripe_subscription_id="sub_ref_r",
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        db.add(sub)
        db.commit()
        sub_id = sub.id

        # Referred user.
        referred = User(email="ref-grant-d@example.com", is_active=True)
        db.add(referred)
        db.commit()
        apply_referral(db, referred, code)
        db.commit()

        grant = grant_first_paid_bonus(db, referred)
        db.commit()
        assert grant is not None
        assert grant.bonus_days == BONUS_DAYS_FIRST_PAID

        sub_reloaded = db.get(Subscription, sub_id)
        assert sub_reloaded is not None
        assert sub_reloaded.expires_at is not None
        # 2030-01-01 + 7 days
        assert sub_reloaded.expires_at >= datetime(2030, 1, 8, tzinfo=timezone.utc)


def test_grant_first_paid_bonus_is_idempotent() -> None:
    """Calling twice never grants twice (unique constraint enforced)."""
    with db_session.SessionLocal() as db:
        ref = User(email="ref-idem-r@example.com", is_active=True)
        db.add(ref)
        db.commit()
        ensure_referral_code(db, ref)
        referred = User(
            email="ref-idem-d@example.com",
            is_active=True,
            referred_by_user_id=ref.id,
        )
        db.add(referred)
        db.commit()

        g1 = grant_first_paid_bonus(db, referred)
        db.commit()
        assert g1 is not None

        g2 = grant_first_paid_bonus(db, referred)
        db.commit()
        assert g2 is None

        rows = list(
            db.execute(
                select(ReferralGrant).where(
                    ReferralGrant.referred_user_id == referred.id
                )
            ).scalars()
        )
        assert len(rows) == 1


def test_grant_no_referrer_returns_none() -> None:
    with db_session.SessionLocal() as db:
        u = User(email="ref-none@example.com", is_active=True)
        db.add(u)
        db.commit()
        assert grant_first_paid_bonus(db, u) is None


# ---------- end-to-end through auth + webhook ----------

def test_magic_link_with_ref_links_referrer(client: TestClient) -> None:
    """Verify token carries `ref` -> exchange persists referred_by_user_id."""
    # Step 1: create referrer & code.
    _login(client, "ref-e2e-r@example.com")
    referrer = _user("ref-e2e-r@example.com")
    with db_session.SessionLocal() as db:
        u = db.get(User, referrer.id)
        ensure_referral_code(db, u)
        db.commit()
        code = u.referral_code
        assert code

    # Step 2: referred user logs in with that code embedded in the magic token.
    _login_with_ref(client, "ref-e2e-d@example.com", code)
    referred = _user("ref-e2e-d@example.com")
    assert referred is not None
    assert referred.referred_by_user_id == referrer.id


def test_first_paid_webhook_grants_bonus(client: TestClient) -> None:
    """checkout.session.completed handler should issue a referral grant."""
    # Build referrer with an active recurring sub.
    _login(client, "wh-ref-r@example.com")
    referrer = _user("wh-ref-r@example.com")
    with db_session.SessionLocal() as db:
        u = db.get(User, referrer.id)
        ensure_referral_code(db, u)
        sub = Subscription(
            user_id=u.id,
            plan="weekly_pro",
            status="active",
            provider="stripe",
            stripe_subscription_id="sub_wh_ref_r",
            expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        db.add(sub)
        db.commit()
        code = u.referral_code

    # Referred user signs up with the code.
    _login_with_ref(client, "wh-ref-d@example.com", code)
    referred = _user("wh-ref-d@example.com")

    event = {
        "id": "evt_ref_paid_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_ref_paid_1",
                "client_reference_id": str(referred.id),
                "subscription": "sub_ref_paid_1",
                "customer": "cus_ref_paid_1",
                "amount_total": 2990,
                "currency": "cny",
                "metadata": {"plan": "weekly_pro", "user_id": str(referred.id)},
            }
        },
    }
    with db_session.SessionLocal() as db:
        out = handle_event(db, event)
    assert out["status"] == "ok"

    with db_session.SessionLocal() as db:
        grants = list(
            db.execute(
                select(ReferralGrant).where(
                    ReferralGrant.referred_user_id == referred.id
                )
            ).scalars()
        )
        assert len(grants) == 1
        assert grants[0].referrer_user_id == referrer.id
        assert grants[0].bonus_days == BONUS_DAYS_FIRST_PAID


# ---------- /api/auth/me referral surface ----------

def test_me_returns_referral_url(client: TestClient) -> None:
    headers = _login(client, "ref-me@example.com")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["referral_code"]
    assert body["referral_url"]
    assert body["referral_code"] in body["referral_url"]


# ---------- admin gating ----------

def test_admin_stats_requires_admin(client: TestClient) -> None:
    headers = _login(client, "admin-no@example.com")
    r = client.get("/api/admin/stats", headers=headers)
    assert r.status_code == 403


def test_admin_stats_works_for_admin(client: TestClient) -> None:
    headers = _login(client, "admin-yes@example.com")
    user = _user("admin-yes@example.com")
    with db_session.SessionLocal() as db:
        u = db.get(User, user.id)
        u.is_admin = True
        db.commit()

    r = client.get("/api/admin/stats", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "cards" in body
    assert "plans" in body
    assert "recent_events" in body
    assert "top_referrers" in body
    # We've created users + at least one stripe sub through prior tests.
    labels = {c["label"] for c in body["cards"]}
    assert "Users" in labels
    assert "Active subs" in labels


# ---------- email template smoke ----------

def test_email_templates_render_text_and_html() -> None:
    s, t, h = et.waitlist_welcome("foo@example.com")
    assert "DemandRadar" in s
    assert "foo@example.com" in t
    assert "<html" in h.lower()

    s2, t2, h2 = et.login_welcome(
        "bar@example.com", referral_url="https://x/?ref=AAA"
    )
    assert "bar@example.com" in t2
    assert "AAA" in h2

    s3, t3, h3 = et.paid_confirmation(
        "baz@example.com",
        plan="weekly_pro",
        amount_cents=2990,
        currency="cny",
        brief_id=None,
    )
    assert "Pro" in s3 or "周报" in s3
    assert "baz@example.com" in t3
    assert "29.90" in t3 or "29.9" in t3

    s4, _t4, h4 = et.referral_bonus(
        "ref@example.com", referred_email="d@example.com", bonus_days=7
    )
    assert "7" in s4
    assert "d@example.com" in h4
