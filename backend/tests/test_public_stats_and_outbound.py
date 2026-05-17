"""Smoke tests for the new public-stats endpoints and the Weibo +
GitHub-sync modules added alongside the launch-readiness work.

Goal: catch regressions in routing / DB queries / config wiring without
hitting external APIs (we monkeypatch httpx for that).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import session as db_session
from app.db.session import Base, SessionLocal
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal
from app.models.social_post import SocialPost
from app.models.weekly_report import WeeklyReport
from app.api import public_stats as ps_mod
from app.notify import github_sync, weibo


@pytest.fixture(autouse=True)
def _clean_per_test():
    # Invalidate the public_stats in-process cache so tests can assert on fresh data.
    ps_mod._CACHE.clear()
    yield
    ps_mod._CACHE.clear()
    with db_session.engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())


def _seed_painpoint(db, score: float = 90.0) -> PainPoint:
    pp = PainPoint(
        pain="Two-way Notion sync for slow networks",
        scenario="V2EX threads",
        target_user="indie devs",
        frequency_signal="weekly",
        emotion="frustrated",
        willingness_to_pay_signal="strong",
        total_score=score,
        go_no_go="go",
    )
    db.add(pp)
    db.commit()
    db.refresh(pp)
    return pp


def _seed_brief(db, pp: PainPoint) -> Brief:
    b = Brief(
        pain_point_id=pp.id,
        title="Notion two-way local-first sync",
        markdown="# Brief\n\nFull content goes here.",
        visibility="public",
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def _seed_weekly(db, pp_ids: list[int]) -> WeeklyReport:
    now = datetime.now(tz=timezone.utc)
    r = WeeklyReport(
        issue_no=1,
        title="Issue #1",
        period_start=now,
        period_end=now,
        markdown_full="x",
        markdown_preview="x",
        pain_point_ids=pp_ids,
        status="published",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ============================================================================
# /api/public/stats
# ============================================================================


def test_public_stats_returns_zeroes_on_empty_db(client: TestClient) -> None:
    r = client.get("/api/public/stats")
    assert r.status_code == 200
    body = r.json()
    for key in ("users", "subscribers", "weekly_issues", "briefs", "signals_scanned"):
        assert body[key] == 0
    assert body["mrr_usd"] == 0.0


def test_public_stats_counts_after_seeding(client: TestClient) -> None:
    with SessionLocal() as db:
        pp = _seed_painpoint(db)
        _seed_brief(db, pp)
        _seed_weekly(db, [pp.id])
        # one raw signal so signals_scanned > 0
        db.add(
            RawSignal(
                source="hn",
                source_item_id="t1",
                title="t",
                url="https://example.com/x",
                text="content",
                collected_at=datetime.now(tz=timezone.utc),
            )
        )
        db.commit()

    r = client.get("/api/public/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["pain_points_scored"] == 1
    assert body["briefs"] == 1
    assert body["weekly_issues"] == 1
    assert body["signals_scanned"] == 1
    assert body["last_issue_at"] is not None
    assert body["last_brief_at"] is not None


# ============================================================================
# /api/public/status
# ============================================================================


def test_public_status_returns_payload(client: TestClient) -> None:
    r = client.get("/api/public/status")
    assert r.status_code == 200
    body = r.json()
    assert body["overall"] in {"healthy", "degraded", "down"}
    assert body["api"] == "ok"
    assert isinstance(body["sources"], list)
    assert isinstance(body["recent_issues"], list)


# ============================================================================
# Weibo poster (composer + queue idempotency, no real HTTP)
# ============================================================================


def test_weibo_compose_weekly_truncates() -> None:
    pp = PainPoint(
        pain="x" * 500,
        scenario=None,
        target_user="indie devs",
        frequency_signal="weekly",
        emotion="frustrated",
        willingness_to_pay_signal="strong",
        total_score=90.0,
        go_no_go="go",
    )
    report = WeeklyReport(
        issue_no=42,
        title="t",
        period_start=datetime.now(tz=timezone.utc),
        period_end=datetime.now(tz=timezone.utc),
        markdown_full="",
        markdown_preview="",
        pain_point_ids=[],
        status="published",
    )
    text = weibo._compose_weekly(report, pp)
    assert "DemandRadar" in text
    assert len(text) <= weibo.WEIBO_MAX


def test_weibo_enqueue_idempotent() -> None:
    with SessionLocal() as db:
        pp = _seed_painpoint(db)
        report = _seed_weekly(db, [pp.id])
        a = weibo.enqueue_weekly_post(db, report)
        db.commit()
        b = weibo.enqueue_weekly_post(db, report)
        db.commit()
        assert a.id == b.id
        # Defaults: WEIBO_ENABLED=false, so status is 'manual'.
        assert a.platform == "weibo"
        assert a.status == "manual"


def test_weibo_brief_skips_low_score() -> None:
    with SessionLocal() as db:
        pp = _seed_painpoint(db, score=10.0)
        b = _seed_brief(db, pp)
        out = weibo.enqueue_brief_post(db, b)
        assert out is None
        # No row inserted.
        rows = db.query(SocialPost).filter_by(platform="weibo").all()
        assert rows == []


def test_weibo_post_pending_noop_when_disabled() -> None:
    # Default settings.weibo_enabled is False — make sure we early-return.
    with SessionLocal() as db:
        stats = weibo.post_pending(db)
        assert stats.posted == 0
        assert stats.failed == 0


# ============================================================================
# GitHub sync (push_brief monkeypatched)
# ============================================================================


def test_github_sync_skips_when_disabled() -> None:
    with SessionLocal() as db:
        pp = _seed_painpoint(db)
        b = _seed_brief(db, pp)
        # By default github_sync_enabled=false.
        assert github_sync.push_brief(db, b) is False


def test_github_sync_skips_low_score(monkeypatch) -> None:
    monkeypatch.setattr(settings, "github_sync_enabled", True)
    monkeypatch.setattr(settings, "github_sync_token", "fake")
    monkeypatch.setattr(settings, "github_sync_repo", "demandradar/briefs")
    monkeypatch.setattr(settings, "github_sync_min_score", 80.0)
    with SessionLocal() as db:
        pp = _seed_painpoint(db, score=50.0)
        b = _seed_brief(db, pp)
        # Should refuse without making HTTP calls.
        assert github_sync.push_brief(db, b) is False


def test_github_sync_pushes_eligible_brief(monkeypatch) -> None:
    monkeypatch.setattr(settings, "github_sync_enabled", True)
    monkeypatch.setattr(settings, "github_sync_token", "fake")
    monkeypatch.setattr(settings, "github_sync_repo", "demandradar/briefs")
    monkeypatch.setattr(settings, "github_sync_branch", "main")
    monkeypatch.setattr(settings, "github_sync_min_score", 80.0)

    captured: dict[str, object] = {}

    class FakeResponse:
        def __init__(self, status_code: int, body: dict | None = None) -> None:
            self.status_code = status_code
            self._body = body or {}
            self.text = "{}"

        def json(self) -> dict:
            return self._body

    class FakeClient:
        def __init__(self, *_, **__):  # type: ignore[no-untyped-def]
            pass

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, *exc):  # type: ignore[no-untyped-def]
            return False

        def get(self, url, params=None):  # type: ignore[no-untyped-def]
            captured.setdefault("get_url", url)
            return FakeResponse(404)  # not yet present → fresh create

        def put(self, url, json=None):  # type: ignore[no-untyped-def]
            captured["put_url"] = url
            captured["put_payload"] = json
            return FakeResponse(201, {"content": {"sha": "abc"}})

    monkeypatch.setattr(github_sync.httpx, "Client", FakeClient)

    with SessionLocal() as db:
        pp = _seed_painpoint(db, score=92.0)
        b = _seed_brief(db, pp)
        assert github_sync.push_brief(db, b) is True

    assert "demandradar/briefs" in str(captured["put_url"])
    payload = captured["put_payload"]
    assert isinstance(payload, dict)
    assert payload["branch"] == "main"
    assert "content" in payload
    assert "sha" not in payload  # fresh create
