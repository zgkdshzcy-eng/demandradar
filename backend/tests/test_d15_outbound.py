"""D15 outbound automation tests: unsubscribe tokens, newsletter dispatcher,
X tweet composer, ProductHunt queue, /rss-friendly admin endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import unsubscribe as unsub_mod
from app.core.security import issue_magic_link_token
from app.db import session as db_session
from app.db.session import Base
from app.models.brief import Brief
from app.models.email_dispatch import EmailDispatch
from app.models.pain_point import PainPoint
from app.models.social_post import SocialPost
from app.models.user import User
from app.models.waitlist import WaitlistEntry
from app.models.weekly_report import WeeklyReport
from app.notify import newsletter as nl_mod
from app.notify.newsletter import dispatch_weekly
from app.notify.producthunt import enqueue_for_brief, list_candidates
from app.notify.twitter import (
    PostStats,
    _compose_weekly_tweet,
    enqueue_weekly_post,
    post_pending,
)


# Each test in this file builds its own deterministic data set, so wipe the
# in-memory DB between tests rather than letting state bleed.
@pytest.fixture(autouse=True)
def _clean_per_test():
    yield
    with db_session.engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())


# -------- helpers --------

def _login(client: TestClient, email: str) -> dict[str, str]:
    token = issue_magic_link_token(email)
    r = client.post("/api/auth/exchange", json={"token": token})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_report(db, issue_no: int = 1, painpoint_ids: list[int] | None = None) -> WeeklyReport:
    now = datetime.now(tz=timezone.utc)
    r = WeeklyReport(
        issue_no=issue_no,
        title=f"DemandRadar 周报 #{issue_no}",
        period_start=now,
        period_end=now,
        markdown_full="# Full\n\n…",
        markdown_preview="# Preview\n\n本期 Top 1: foo\n本期 Top 2: bar\n",
        pain_point_ids=painpoint_ids or [],
        status="published",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ============================================================================
# 1. unsubscribe tokens
# ============================================================================

class TestUnsubscribeTokens:
    def test_round_trip(self) -> None:
        tok = unsub_mod.make_token("foo@example.com", "user")
        assert tok.count(".") == 2
        parsed = unsub_mod.verify_token(tok)
        assert parsed == ("foo@example.com", "user")

    def test_case_normalised(self) -> None:
        tok = unsub_mod.make_token("FOO@example.com", "wait")
        parsed = unsub_mod.verify_token(tok)
        assert parsed == ("foo@example.com", "wait")

    def test_tampered_signature_rejected(self) -> None:
        tok = unsub_mod.make_token("foo@example.com", "user")
        bad = tok[:-5] + "abcde"
        assert unsub_mod.verify_token(bad) is None

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError):
            unsub_mod.make_token("foo@example.com", "bogus")

    def test_garbage_input_returns_none(self) -> None:
        assert unsub_mod.verify_token("not.a.token") is None
        assert unsub_mod.verify_token("") is None


# ============================================================================
# 2. newsletter dispatcher
# ============================================================================

class TestDispatcher:
    def test_dry_run_counts_recipients_without_sending(self, monkeypatch) -> None:
        # Force smtp_enabled true so the dispatcher does its full work.
        monkeypatch.setattr(nl_mod, "smtp_enabled", lambda: True)

        with db_session.SessionLocal() as db:
            db.add_all([
                User(email="a@example.com", is_active=True),
                User(email="b@example.com", is_active=True),
                User(email="opt-out@example.com", is_active=True,
                     unsubscribed_at=datetime.now(tz=timezone.utc)),
                WaitlistEntry(email="c@example.com"),
                # de-dup with users.email
                WaitlistEntry(email="a@example.com"),
            ])
            r = _seed_report(db, issue_no=11)
            stats = dispatch_weekly(db, r, dry_run=True)

        assert stats.candidates == 3  # a, b, c (opt-out excluded; a dedup'd)
        assert stats.sent == 3
        assert stats.failed == 0
        assert stats.smtp_disabled is False

    def test_sends_and_logs_one_dispatch_per_recipient(self, monkeypatch) -> None:
        sent_to: list[str] = []

        def fake_send(*, to, subject, text, html=None):  # type: ignore[no-untyped-def]
            sent_to.append(to)
            return True

        monkeypatch.setattr(nl_mod, "smtp_enabled", lambda: True)
        monkeypatch.setattr(nl_mod, "send_email", fake_send)
        monkeypatch.setattr(nl_mod.settings, "newsletter_dispatch_per_minute", 6000, raising=False)

        with db_session.SessionLocal() as db:
            db.add(User(email="a@example.com", is_active=True))
            db.add(WaitlistEntry(email="b@example.com"))
            r = _seed_report(db, issue_no=12)
            stats = dispatch_weekly(db, r)
        assert sorted(sent_to) == ["a@example.com", "b@example.com"]
        assert stats.sent == 2 and stats.skipped == 0 and stats.failed == 0

        with db_session.SessionLocal() as db:
            rows = list(db.execute(select(EmailDispatch)).scalars())
        assert {r.email for r in rows} == {"a@example.com", "b@example.com"}
        assert all(r.status == "sent" and r.sent_at is not None for r in rows)
        assert {r.weekly_report_id for r in rows} == {rows[0].weekly_report_id}

    def test_idempotent_second_dispatch_skips(self, monkeypatch) -> None:
        calls = {"n": 0}

        def fake_send(*, to, subject, text, html=None):  # type: ignore[no-untyped-def]
            calls["n"] += 1
            return True

        monkeypatch.setattr(nl_mod, "smtp_enabled", lambda: True)
        monkeypatch.setattr(nl_mod, "send_email", fake_send)
        monkeypatch.setattr(nl_mod.settings, "newsletter_dispatch_per_minute", 6000, raising=False)

        with db_session.SessionLocal() as db:
            db.add(User(email="ide@example.com", is_active=True))
            r = _seed_report(db, issue_no=13)
            s1 = dispatch_weekly(db, r)
            s2 = dispatch_weekly(db, r)
        assert s1.sent == 1
        assert s2.sent == 0
        assert s2.skipped == 1
        assert calls["n"] == 1

    def test_smtp_disabled_short_circuits(self, monkeypatch) -> None:
        monkeypatch.setattr(nl_mod, "smtp_enabled", lambda: False)
        with db_session.SessionLocal() as db:
            db.add(User(email="x@example.com", is_active=True))
            r = _seed_report(db, issue_no=14)
            stats = dispatch_weekly(db, r)
        assert stats.smtp_disabled is True
        assert stats.sent == 0


# ============================================================================
# 3. /api/newsletter/unsubscribe
# ============================================================================

class TestUnsubscribeEndpoint:
    def test_user_unsubscribe_flips_flag(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            db.add(User(email="user-unsub@example.com", is_active=True))
            db.commit()
        tok = unsub_mod.make_token("user-unsub@example.com", "user")
        r = client.get("/api/newsletter/unsubscribe", params={"token": tok})
        assert r.status_code == 200
        assert "退订成功" in r.text

        with db_session.SessionLocal() as db:
            u = db.scalar(select(User).where(User.email == "user-unsub@example.com"))
            assert u is not None and u.unsubscribed_at is not None

    def test_waitlist_unsubscribe_flips_flag(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            db.add(WaitlistEntry(email="wait-unsub@example.com"))
            db.commit()
        tok = unsub_mod.make_token("wait-unsub@example.com", "wait")
        r = client.get("/api/newsletter/unsubscribe", params={"token": tok})
        assert r.status_code == 200

        with db_session.SessionLocal() as db:
            e = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == "wait-unsub@example.com"))
            assert e is not None and e.unsubscribed_at is not None

    def test_invalid_token_returns_400(self, client: TestClient) -> None:
        r = client.get("/api/newsletter/unsubscribe", params={"token": "garbage"})
        assert r.status_code == 400
        assert "链接无效" in r.text

    def test_missing_token_returns_400(self, client: TestClient) -> None:
        r = client.get("/api/newsletter/unsubscribe")
        assert r.status_code == 400


# ============================================================================
# 4. X (Twitter) composer + queue
# ============================================================================

class TestTwitter:
    def test_compose_with_top_painpoint_under_280(self) -> None:
        with db_session.SessionLocal() as db:
            pp = PainPoint(
                pain="批量给 PDF 加水印太慢，需要桌面版工具",
                target_user="独立设计师",
                total_score=88.5,
                go_no_go="go",
            )
            db.add(pp)
            db.commit()
            r = _seed_report(db, issue_no=21, painpoint_ids=[pp.id])
            text = _compose_weekly_tweet(r, pp)
        assert len(text) <= 280
        assert "DemandRadar" in text
        assert "#21" in text or "21" in text
        assert "score 89" in text or "score 88" in text

    def test_compose_without_painpoint_uses_fallback(self) -> None:
        with db_session.SessionLocal() as db:
            r = _seed_report(db, issue_no=22)
            text = _compose_weekly_tweet(r, None)
        assert "DemandRadar" in text
        assert "#22" in text
        assert len(text) <= 280

    def test_long_painpoint_is_truncated_to_fit_280(self) -> None:
        with db_session.SessionLocal() as db:
            pp = PainPoint(
                pain="很长的痛点描述 " * 50,
                target_user="独立开发者社区里同时使用 macOS 和 Windows 的全栈工程师",
                total_score=99.0,
                go_no_go="go",
            )
            db.add(pp)
            db.commit()
            r = _seed_report(db, issue_no=23, painpoint_ids=[pp.id])
            text = _compose_weekly_tweet(r, pp)
        assert len(text) <= 280

    def test_enqueue_is_idempotent(self) -> None:
        with db_session.SessionLocal() as db:
            r = _seed_report(db, issue_no=24)
            row1 = enqueue_weekly_post(db, r)
            db.commit()
            row2 = enqueue_weekly_post(db, r)
            db.commit()
        assert row1.id == row2.id
        with db_session.SessionLocal() as db:
            n = db.scalar(
                select(SocialPost.id).where(SocialPost.weekly_report_id == r.id)
            )
            assert n is not None

    def test_status_manual_when_disabled(self, monkeypatch) -> None:
        monkeypatch.setattr(nl_mod.settings, "twitter_enabled", False, raising=False)
        with db_session.SessionLocal() as db:
            r = _seed_report(db, issue_no=25)
            row = enqueue_weekly_post(db, r)
            db.commit()
        assert row.status == "manual"

    def test_post_pending_no_op_when_disabled(self, monkeypatch) -> None:
        from app.notify import twitter as tw
        monkeypatch.setattr(tw.settings, "twitter_enabled", False, raising=False)
        with db_session.SessionLocal() as db:
            stats = post_pending(db)
        assert isinstance(stats, PostStats)
        assert stats.posted == 0 and stats.failed == 0

    def test_post_pending_marks_failed_without_token(self, monkeypatch) -> None:
        from app.notify import twitter as tw
        monkeypatch.setattr(tw.settings, "twitter_enabled", True, raising=False)
        monkeypatch.setattr(tw.settings, "twitter_access_token", "", raising=False)
        with db_session.SessionLocal() as db:
            r = _seed_report(db, issue_no=26)
            row = enqueue_weekly_post(db, r)
            row.status = "queued"
            db.commit()
            stats = post_pending(db)
        assert stats.failed == 1
        with db_session.SessionLocal() as db:
            row2 = db.scalar(select(SocialPost).where(SocialPost.weekly_report_id == r.id))
            assert row2 is not None
            assert row2.status == "failed"
            assert "missing" in (row2.error or "").lower()


# ============================================================================
# 5. ProductHunt candidate queue
# ============================================================================

class TestProductHunt:
    def test_enqueue_for_brief_creates_manual_row(self) -> None:
        with db_session.SessionLocal() as db:
            pp = PainPoint(pain="ph-test pain", target_user="indie devs", total_score=92.0)
            db.add(pp)
            db.flush()
            b = Brief(
                pain_point_id=pp.id,
                title="My Demand Radar Brief",
                markdown="# Brief\n\nFull body",
                visibility="paid",
                version=1,
            )
            db.add(b)
            db.commit()
            row = enqueue_for_brief(db, b)
            db.commit()

        assert row is not None
        assert row.platform == "producthunt"
        assert row.status == "manual"
        assert row.kind == "brief"
        assert "Tagline" in row.body
        assert "indie devs" in row.body or "indie devs" in row.body.lower()

    def test_enqueue_for_brief_is_idempotent(self) -> None:
        with db_session.SessionLocal() as db:
            pp = PainPoint(pain="ph-idem", target_user="x")
            db.add(pp)
            db.flush()
            b = Brief(pain_point_id=pp.id, title="Idem", markdown="m", visibility="paid")
            db.add(b)
            db.commit()
            r1 = enqueue_for_brief(db, b)
            db.commit()
            r2 = enqueue_for_brief(db, b)
            db.commit()
        assert r1 is not None and r2 is not None and r1.id == r2.id

    def test_list_candidates_orders_recent_first(self) -> None:
        with db_session.SessionLocal() as db:
            pp = PainPoint(pain="ph-list")
            db.add(pp)
            db.flush()
            for i in range(3):
                b = Brief(
                    pain_point_id=pp.id,
                    title=f"Brief {i}",
                    markdown="m",
                    visibility="paid",
                )
                db.add(b)
                db.flush()
                enqueue_for_brief(db, b)
            db.commit()
            rows = list_candidates(db, limit=2)
        assert len(rows) == 2
        assert rows[0].id > rows[1].id


# ============================================================================
# 6. admin endpoints surface dispatches + social posts
# ============================================================================

class TestAdminEndpoints:
    def _admin_headers(self, client: TestClient, email: str) -> dict[str, str]:
        headers = _login(client, email)
        with db_session.SessionLocal() as db:
            u = db.scalar(select(User).where(User.email == email))
            u.is_admin = True
            db.commit()
        return headers

    def test_dispatches_endpoint_returns_rows(self, client: TestClient) -> None:
        # Seed a dispatch row directly so the endpoint has data to return.
        with db_session.SessionLocal() as db:
            db.add(
                EmailDispatch(
                    campaign="weekly:99",
                    email="r@example.com",
                    status="sent",
                    sent_at=datetime.now(tz=timezone.utc),
                )
            )
            db.commit()
        h = self._admin_headers(client, "admin-d15-1@example.com")
        r = client.get(
            "/api/admin/dispatches", params={"campaign": "weekly:99"}, headers=h
        )
        assert r.status_code == 200
        body = r.json()
        assert body["campaign"] == "weekly:99"
        assert any(row["email"] == "r@example.com" for row in body["rows"])
        assert body["summary"].get("sent", 0) >= 1

    def test_social_posts_endpoint_filters(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            r = _seed_report(db, issue_no=77)
            enqueue_weekly_post(db, r)
            db.commit()
        h = self._admin_headers(client, "admin-d15-2@example.com")
        r = client.get("/api/admin/social-posts", params={"platform": "x"}, headers=h)
        assert r.status_code == 200
        rows = r.json()
        assert any(row["kind"] == "weekly" for row in rows)

    def test_dispatches_requires_admin(self, client: TestClient) -> None:
        h = _login(client, "noadmin-d15@example.com")
        r = client.get("/api/admin/dispatches", headers=h)
        assert r.status_code == 403
