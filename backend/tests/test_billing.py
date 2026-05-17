"""Billing redeem flow + entitlement-gated brief/weekly access."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.security import issue_magic_link_token, issue_redeem_code
from app.db.session import SessionLocal
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.weekly_report import WeeklyReport


def _login(client: TestClient, email: str) -> dict[str, str]:
    """Returns a Bearer header for `email` (creates the user if needed)."""
    token = issue_magic_link_token(email)
    r = client.post("/api/auth/exchange", json={"token": token})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _ensure_paid_brief() -> int:
    """Insert one paid brief + its parent pain point. Returns brief id."""
    with SessionLocal() as db:
        pp = PainPoint(pain="ent-test pain", target_user="x")
        db.add(pp)
        db.flush()
        b = Brief(
            pain_point_id=pp.id,
            title="Ent-test brief",
            markdown="# Locked\n\nSecret content.",
            visibility="paid",
            version=1,
        )
        db.add(b)
        db.commit()
        db.refresh(b)
        return b.id


def _ensure_weekly() -> int:
    """Insert one weekly report. Returns issue_no."""
    with SessionLocal() as db:
        existing = db.query(WeeklyReport).first()
        if existing is not None:
            return existing.issue_no
        wr = WeeklyReport(
            issue_no=9999,
            title="Ent-test weekly",
            period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2026, 1, 7, tzinfo=timezone.utc),
            markdown_preview="preview only",
            markdown_full="full content here",
            pain_point_ids=[],
            status="draft",
        )
        db.add(wr)
        db.commit()
        db.refresh(wr)
        return wr.issue_no


def test_redeem_weekly_pro_unlocks_weekly_full(client: TestClient) -> None:
    issue = _ensure_weekly()
    headers = _login(client, "weekly-buyer@example.com")

    # Locked first.
    r = client.get(f"/api/weekly/{issue}", headers=headers)
    assert r.status_code == 200
    assert r.json()["unlocked"] is False
    assert r.json().get("markdown_full") is None

    code = issue_redeem_code("weekly_pro", days=30)
    r = client.post("/api/billing/redeem", json={"code": code}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "weekly_pro"
    assert body["entitlement"]["can_read_weekly_full"] is True

    r = client.get(f"/api/weekly/{issue}", headers=headers)
    assert r.json()["unlocked"] is True
    assert r.json()["markdown_full"] == "full content here"


def test_redeem_brief_oneoff_unlocks_only_that_brief(client: TestClient) -> None:
    bid = _ensure_paid_brief()
    other_bid = _ensure_paid_brief()
    headers = _login(client, "brief-buyer@example.com")

    code = issue_redeem_code("brief_oneoff", days=0, brief_id=bid)
    r = client.post("/api/billing/redeem", json={"code": code}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["entitlement"]["can_read_any_brief"] is False
    assert bid in r.json()["entitlement"]["unlocked_brief_ids"]

    # Target brief: full markdown unlocked.
    r1 = client.get(f"/api/briefs/{bid}", headers=headers)
    assert r1.json()["unlocked"] is True
    assert "Secret content" in r1.json()["markdown"]

    # Other paid brief still locked.
    r2 = client.get(f"/api/briefs/{other_bid}", headers=headers)
    assert r2.json()["unlocked"] is False


def test_redeem_code_cannot_be_used_twice(client: TestClient) -> None:
    headers = _login(client, "double-spend@example.com")
    code = issue_redeem_code("weekly_pro", days=7)
    r1 = client.post("/api/billing/redeem", json={"code": code}, headers=headers)
    assert r1.status_code == 200
    r2 = client.post("/api/billing/redeem", json={"code": code}, headers=headers)
    assert r2.status_code == 409


def test_redeem_requires_login(client: TestClient) -> None:
    code = issue_redeem_code("weekly_pro", days=30)
    r = client.post("/api/billing/redeem", json={"code": code})
    assert r.status_code == 401


def test_brief_oneoff_requires_brief_id(client: TestClient) -> None:
    headers = _login(client, "no-brief-id@example.com")
    code = issue_redeem_code("brief_oneoff", days=0)  # missing brief_id
    r = client.post("/api/billing/redeem", json={"code": code}, headers=headers)
    assert r.status_code == 400


def test_subscription_endpoint_lists_active_rows(client: TestClient) -> None:
    headers = _login(client, "subs-list@example.com")
    code = issue_redeem_code("weekly_pro", days=14)
    client.post("/api/billing/redeem", json={"code": code}, headers=headers)

    r = client.get("/api/billing/subscription", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["plan"] == "weekly_pro"
    assert body["entitlement"]["can_read_weekly_full"] is True


def test_admin_master_token_still_unlocks(client: TestClient) -> None:
    """Backward-compat: APP_SECRET_KEY in X-Unlock-Token (or query) bypasses entitlement."""
    from app.core.config import settings

    bid = _ensure_paid_brief()
    r = client.get(
        f"/api/briefs/{bid}/markdown",
        headers={"X-Unlock-Token": settings.app_secret_key},
    )
    assert r.status_code == 200
    assert "Secret content" in r.text
