"""Tests for D19 operational automation features."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.brief import Brief
from app.models.email_dispatch import EmailDispatch
from app.models.pain_point import PainPoint
from app.models.subscription import Subscription
from app.models.user import User


# ── 1. Admin alert (core/alert.py) ──────────────────────────────────────

class TestNotifyAdmin:
    def test_disabled_when_url_empty(self):
        from app.core.alert import notify_admin

        with patch("app.core.alert.settings") as mock_s:
            mock_s.admin_webhook_url = ""
            mock_s.app_env = "test"
            assert notify_admin("hi") is False

    def test_sends_when_url_set(self):
        from app.core.alert import notify_admin

        with patch("app.core.alert.settings") as mock_s, \
             patch("app.core.alert.httpx.Client") as mock_client_cls:
            mock_s.admin_webhook_url = "https://hooks.slack.com/fake"
            mock_s.app_env = "test"
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            mock_client = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            ok = notify_admin("test title", "body", level="warn", key=None)
            assert ok is True
            call_args = mock_client.post.call_args
            payload = json.loads(call_args.kwargs["content"])
            assert "test title" in payload["text"]

    def test_throttle_blocks_repeat(self):
        from app.core.alert import notify_admin, _LAST_SENT_AT

        with patch("app.core.alert.settings") as mock_s, \
             patch("app.core.alert.httpx.Client") as mock_client_cls:
            mock_s.admin_webhook_url = "https://hooks.slack.com/fake"
            mock_s.app_env = "test"
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            mock_client = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            _LAST_SENT_AT.clear()
            ok1 = notify_admin("t", key="k1", throttle_seconds=600)
            ok2 = notify_admin("t", key="k1", throttle_seconds=600)
            assert ok1 is True
            assert ok2 is False  # throttled


# ── 2. Email retry (notify/retry.py) ────────────────────────────────────

class TestRetryFailed:
    def test_no_failed_rows(self):
        from app.notify.retry import retry_failed

        with SessionLocal() as db:
            stats = retry_failed(db, limit=10)
            assert stats.candidates == 0

    def test_retries_mark_sent(self):
        from app.notify.retry import retry_failed

        with SessionLocal() as db:
            # Insert a failed dispatch row with updated_at in the past so it
            # passes the COOLDOWN_MINUTES filter (no weekly_report_id → exhausted).
            old_ts = datetime.now(tz=timezone.utc) - timedelta(hours=2)
            row = EmailDispatch(
                campaign="newsletter",
                email="test@example.com",
                status="failed",
                attempts=1,
                error="smtp timeout",
                updated_at=old_ts,
            )
            db.add(row)
            db.commit()

            with patch("app.notify.retry.smtp_enabled", return_value=True):
                stats = retry_failed(db, limit=10)
            # Without a weekly_report_id the row is marked exhausted.
            assert stats.candidates == 1
            assert stats.exhausted == 1


# ── 3. Expire redeem subs (billing/expire.py) ───────────────────────────

class TestExpireRedeem:
    def test_no_expired(self):
        from app.billing.expire import expire_redeem_subs

        with SessionLocal() as db:
            stats = expire_redeem_subs(db)
            assert stats.scanned == 0

    def test_expires_past_date(self):
        from app.billing.expire import expire_redeem_subs

        with SessionLocal() as db:
            u = User(email="expire@test.com")
            db.add(u)
            db.flush()
            sub = Subscription(
                user_id=u.id,
                provider="redeem",
                plan="weekly_pro",
                status="active",
                expires_at=datetime.now(tz=timezone.utc) - timedelta(hours=1),
            )
            db.add(sub)
            db.commit()

            stats = expire_redeem_subs(db)
            assert stats.scanned == 1
            assert stats.expired == 1

            db.refresh(sub)
            assert sub.status == "expired"

    def test_skips_still_active(self):
        from app.billing.expire import expire_redeem_subs

        with SessionLocal() as db:
            u = User(email="active@test.com")
            db.add(u)
            db.flush()
            sub = Subscription(
                user_id=u.id,
                provider="redeem",
                plan="weekly_pro",
                status="active",
                expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
            )
            db.add(sub)
            db.commit()

            stats = expire_redeem_subs(db)
            assert stats.scanned == 0


# ── 4. Source health adaptive throttle ───────────────────────────────────

class TestSourceHealth:
    def test_should_run_normal(self):
        from app.core import source_health

        source_health.reset("test_src")
        assert source_health.should_run("test_src") is True

    def test_backoff_skips_ticks(self):
        from app.core import source_health

        source_health.reset("test_src2")
        # Simulate 4 consecutive failures -> interval_mult goes to 2
        for _ in range(4):
            source_health.record_outcome("test_src2", ok=False, error="oops")
        # should_run returns True only on every 2nd tick
        assert source_health.should_run("test_src2") is False  # tick 5
        assert source_health.should_run("test_src2") is True   # tick 6

    def test_success_resets(self):
        from app.core import source_health

        source_health.reset("test_src3")
        source_health.record_outcome("test_src3", ok=False, error="x")
        source_health.record_outcome("test_src3", ok=True)
        st = source_health.snapshot().get("test_src3", {})
        assert st.get("interval_mult") == 1
        assert st.get("consecutive_failures") == 0


# ── 5. Cold start email (notify/cold_start.py) ──────────────────────────

class TestColdStart:
    def test_no_eligible_users(self):
        from app.notify.cold_start import run

        with SessionLocal() as db:
            stats = run(db, dry_run=True)
            assert stats.candidates == 0

    def test_eligible_user_dry_run(self):
        from app.notify.cold_start import run

        with SessionLocal() as db:
            # User signed up 50h ago, no subscription.
            u = User(
                email="cold@test.com",
                created_at=datetime.now(tz=timezone.utc) - timedelta(hours=50),
            )
            db.add(u)
            # Need at least one go painpoint.
            pp = PainPoint(
                pain="test pain",
                total_score=85.0,
                go_no_go="go",
            )
            db.add(pp)
            db.commit()

            with patch("app.notify.cold_start.settings") as mock_s:
                mock_s.cold_start_window_hours = 48
                stats = run(db, dry_run=True)
            assert stats.candidates == 1
            assert stats.sent == 1


# ── 6. Admin digest (notify/admin_digest.py) ────────────────────────────

class TestAdminDigest:
    def test_collect_returns_stats(self):
        from app.notify.admin_digest import collect

        with SessionLocal() as db:
            stats = collect(db)
            assert hasattr(stats, "new_users")
            assert hasattr(stats, "cards")

    def test_send_skipped_when_no_email(self):
        from app.notify.admin_digest import send_daily_digest

        with SessionLocal() as db, \
             patch("app.notify.admin_digest.settings") as mock_s:
            mock_s.admin_email = ""
            ok = send_daily_digest(db)
            assert ok is False


# ── 7. Brief auto-tweet (notify/twitter.py) ─────────────────────────────

class TestEnqueueBriefPost:
    def test_skips_low_score(self):
        from app.notify.twitter import enqueue_brief_post

        with SessionLocal() as db:
            pp = PainPoint(
                pain="low score",
                total_score=50.0,
                go_no_go="go",
            )
            db.add(pp)
            db.flush()
            b = Brief(pain_point_id=pp.id, title="t", markdown="m", version=1)
            db.add(b)
            db.commit()

            result = enqueue_brief_post(db, b, min_score=80.0)
            assert result is None

    def test_queues_high_score(self):
        from app.notify.twitter import enqueue_brief_post

        with SessionLocal() as db:
            pp = PainPoint(
                pain="high score",
                total_score=90.0,
                go_no_go="go",
            )
            db.add(pp)
            db.flush()
            b = Brief(pain_point_id=pp.id, title="t", markdown="m", version=1)
            db.add(b)
            db.commit()

            with patch("app.notify.twitter.settings") as mock_s:
                mock_s.twitter_enabled = True
                mock_s.auto_tweet_min_score = 80.0
                mock_s.public_base_url = "http://localhost:3000"
                result = enqueue_brief_post(db, b, min_score=80.0)
            assert result is not None
            assert result.kind == "brief"


# ── 8. Payment failed email template ────────────────────────────────────

class TestPaymentFailedTemplate:
    def test_en_locale(self):
        from app.core.email_templates import payment_failed

        subj, txt, html = payment_failed(
            "user@test.com", plan="weekly_pro", locale="en"
        )
        assert "Payment failed" in subj
        # _plan_display converts weekly_pro → "Pro Weekly"
        assert "Pro Weekly" in txt
        assert "<!doctype html>" in html

    def test_zh_locale(self):
        from app.core.email_templates import payment_failed

        subj, txt, html = payment_failed(
            "user@test.com", plan="weekly_pro", locale="zh"
        )
        assert "续费失败" in subj
        # _plan_display converts weekly_pro → "Pro 周报订阅"
        assert "Pro 周报订阅" in txt


# ── 9. Cold start email template ─────────────────────────────────────────

class TestColdStartTemplate:
    def test_en_locale(self):
        from app.core.email_templates import cold_start_top3

        items = [
            {"pain": "p1", "target_user": "devs", "score": 90.0, "pain_point_id": 1},
            {"pain": "p2", "target_user": "founders", "score": 85.0, "pain_point_id": 2},
        ]
        subj, txt, html = cold_start_top3(
            "user@test.com", items=items, locale="en"
        )
        assert "3 high-WTP" in subj
        assert "p1" in txt

    def test_zh_locale(self):
        from app.core.email_templates import cold_start_top3

        items = [{"pain": "测试痛点", "target_user": "开发者", "score": 88.0, "pain_point_id": 1}]
        subj, txt, html = cold_start_top3(
            "user@test.com", items=items, locale="zh"
        )
        assert "3 个" in subj
        assert "测试痛点" in txt
