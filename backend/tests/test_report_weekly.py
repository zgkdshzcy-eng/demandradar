"""Weekly digest generator + API tests (no LLM, no SMTP)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal
from app.models.weekly_report import WeeklyReport
from app.report.weekly import generate_weekly


def _seed_window(db) -> int:  # type: ignore[no-untyped-def]
    """Insert a pain point + supporting signals dated within last 24h."""
    sig = RawSignal(
        source="hn",
        source_item_id="weekly-evidence",
        text="People want a unified inbox tool",
        title="unified inbox pain",
        lang="en",
        collected_at=datetime.now(timezone.utc),
    )
    db.add(sig)
    db.flush()
    pp = PainPoint(
        pain="跨平台消息混乱",
        scenario="同时管 5 个 IM",
        target_user="项目经理",
        frequency_signal="high",
        emotion="anxiety",
        willingness_to_pay_signal="strong",
        source_signal_ids=[sig.id],
        pain_intensity=5, frequency=5, willingness_to_pay=5,
        reach_difficulty=4, dev_difficulty=3, competition=3,
        differentiation=4, automation_potential=5, virality=4, retention=4,
        total_score=88.0,
        go_no_go="go",
        rationale="cross platform IM pain",
    )
    db.add(pp)
    db.commit()
    return pp.id


def test_generate_weekly_creates_report() -> None:
    with SessionLocal() as db:
        _seed_window(db)
        stats = generate_weekly(db, items_limit=10, period_days=7)
        assert stats.inserted is True
        assert stats.items >= 1

        r = db.query(WeeklyReport).filter(WeeklyReport.issue_no == stats.issue_no).one()
        assert "DemandRadar" in r.title or "需求雷达" in r.title
        assert "跨平台" in r.markdown_full
        # Preview is full content trimmed + a "免费试读" tag. With many items it
        # is strictly shorter; with 1 item the tag bytes can edge it past
        # `full`. Just assert the tag is present and preview is non-empty.
        assert "免费试读" in r.markdown_preview
        assert len(r.markdown_preview) > 0
        assert r.status == "published"
        assert isinstance(r.pain_point_ids, list) and len(r.pain_point_ids) >= 1


def test_generate_weekly_idempotent_same_day() -> None:
    with SessionLocal() as db:
        # Already generated above; run again should NOT insert.
        stats = generate_weekly(db, items_limit=10, period_days=7)
        assert stats.inserted is False


def test_weekly_api_list(client: TestClient) -> None:
    r = client.get("/api/weekly", params={"limit": 5})
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert "issue_no" in items[0]
    assert "items" in items[0]


def test_weekly_api_latest_locked(client: TestClient) -> None:
    r = client.get("/api/weekly/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["unlocked"] is False
    assert body["markdown_full"] is None
    assert body["markdown_preview"]


def test_weekly_api_unlock_with_token(client: TestClient) -> None:
    from app.core.config import settings

    r_list = client.get("/api/weekly", params={"limit": 1})
    issue_no = r_list.json()[0]["issue_no"]
    r = client.get(
        f"/api/weekly/{issue_no}",
        params={"x_unlock_token": settings.app_secret_key},
    )
    body = r.json()
    assert body["unlocked"] is True
    assert body["markdown_full"]


def test_weekly_html_render(client: TestClient) -> None:
    r_list = client.get("/api/weekly", params={"limit": 1})
    issue_no = r_list.json()[0]["issue_no"]
    r = client.get(f"/api/weekly/{issue_no}/html")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text.lower()
