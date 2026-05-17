"""Smoke tests for health & waitlist endpoints (uses SQLite via conftest)."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["db"] == "ok"  # SQLite in-memory should be reachable


def test_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "DemandRadar"


def test_waitlist_count_initial(client: TestClient) -> None:
    r = client.get("/api/waitlist/count")
    assert r.status_code == 200
    assert r.json()["count"] >= 0


def test_waitlist_join_and_dedup(client: TestClient) -> None:
    # First insert
    r = client.post("/api/waitlist", json={"email": "alice@example.com", "source": "test"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    first_count = body["count"]
    assert first_count >= 1

    # Same email is idempotent (no count increase)
    r2 = client.post("/api/waitlist", json={"email": "alice@example.com"})
    assert r2.status_code == 200
    assert r2.json()["count"] == first_count

    # Different email increments
    r3 = client.post("/api/waitlist", json={"email": "bob@example.com"})
    assert r3.status_code == 200
    assert r3.json()["count"] == first_count + 1


def test_waitlist_invalid_email(client: TestClient) -> None:
    r = client.post("/api/waitlist", json={"email": "not-an-email"})
    assert r.status_code == 422  # pydantic EmailStr validation
