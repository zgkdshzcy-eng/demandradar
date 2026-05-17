"""End-to-end auth flow over the FastAPI test client."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import issue_magic_link_token
from app.db.session import SessionLocal
from app.models.user import User


def _new_email(suffix: str) -> str:
    return f"auth-{suffix}@example.com"


def test_request_link_creates_user_and_returns_debug_link(client: TestClient) -> None:
    email = _new_email("create")
    r = client.post("/api/auth/request-link", json={"email": email})
    assert r.status_code == 200, r.text
    body = r.json()
    # In dev / no SMTP, the link is returned for inspection.
    assert body["smtp_enabled"] is False
    assert body["debug_link"] and "token=" in body["debug_link"]

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.is_active is True


def test_me_requires_login(client: TestClient) -> None:
    # Use a fresh client to avoid stale cookies.
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_full_login_flow_sets_cookie_and_me_works(client: TestClient) -> None:
    email = _new_email("flow")
    # Fast-path: skip the email round-trip by constructing the magic-link token directly
    # (the API would have done the same).
    token = issue_magic_link_token(email)

    r = client.get("/api/auth/verify", params={"token": token}, follow_redirects=False)
    assert r.status_code == 302
    assert "dr_session" in r.cookies

    me = client.get("/api/auth/me", cookies=r.cookies)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == email
    assert body["entitlement"]["can_read_any_brief"] is False


def test_exchange_returns_bearer(client: TestClient) -> None:
    email = _new_email("bearer")
    token = issue_magic_link_token(email)
    r = client.post("/api/auth/exchange", json={"token": token})
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_verify_rejects_bad_token(client: TestClient) -> None:
    r = client.get("/api/auth/verify", params={"token": "not-a-jwt"})
    assert r.status_code == 400
