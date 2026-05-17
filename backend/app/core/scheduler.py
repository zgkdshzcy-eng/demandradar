"""APScheduler integration: register hourly collector jobs at app startup.

Disabled in test environment (DATABASE_URL points to sqlite). Toggle off via
APP_SCHEDULER_DISABLED=1 if needed.
"""
from __future__ import annotations

import os

import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.collectors import REGISTRY, BaseCollector
from app.core import source_health
from app.core.alert import notify_admin
from app.core.config import settings
from app.core.logging import logger
from app.core.observability import record_job

_scheduler: AsyncIOScheduler | None = None

# (name, interval_minutes, kwargs)
JOB_PLAN: list[tuple[str, int, dict]] = [
    ("hn", 60, {"limit": 200}),
    ("reddit", 60, {"limit": 150}),
    ("v2ex", 120, {"limit": 150}),
    ("producthunt", 360, {"limit": 50}),
    ("github_trending", 720, {"limit": 75}),  # 12h
    ("google_trends", 1440, {"limit": 60}),   # 24h
    # D16: new sources
    ("lobsters", 90, {"limit": 100}),
    ("indiehackers", 240, {"limit": 100}),
    ("weibo", 60, {"limit": 50}),
]

# Pipeline jobs: dedupe + embed + cluster + extract run after collectors.
PIPELINE_PLAN: list[tuple[str, int]] = [
    ("dedupe", 90),
    ("embed", 30),
    ("cluster", 60),
    ("extract", 120),
    ("score", 180),
    ("brief", 240),
]


def _is_disabled() -> bool:
    if os.environ.get("APP_SCHEDULER_DISABLED") == "1":
        return True
    # Disable when running on sqlite (typically tests).
    return "sqlite" in os.environ.get("DATABASE_URL", "")


async def _run_collector(name: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
    cls: type[BaseCollector] | None = REGISTRY.get(name)
    if cls is None:
        logger.warning("scheduler: unknown collector {}", name)
        return
    if not source_health.should_run(name):
        # Adaptive throttling: skip this tick — collector is in backoff.
        record_job(f"collect_{name}", "skipped", 0.0)
        return
    started = time.perf_counter()
    outcome = "ok"
    err_msg: str | None = None
    try:
        await cls(**kwargs).run()
    except Exception as exc:  # noqa: BLE001
        outcome = "error"
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.exception("scheduler: collector {} crashed: {}", name, exc)
    finally:
        record_job(f"collect_{name}", outcome, time.perf_counter() - started)
        st = source_health.record_outcome(name, ok=(outcome == "ok"), error=err_msg)
        # Alert once when we slip into backoff (mult flips from 1 -> >1).
        if outcome != "ok" and st.interval_mult > 1:
            notify_admin(
                f"⚠️ Collector {name} backing off ×{st.interval_mult}",
                f"{st.consecutive_failures} consecutive failures. "
                f"Last error: {st.last_error or 'unknown'}",
                level="warn",
                key=f"collector_backoff:{name}:{st.interval_mult}",
                throttle_seconds=3600,
            )


async def _run_dedupe() -> None:
    from app.db.session import SessionLocal
    from app.pipeline.dedupe import run_dedupe

    try:
        with SessionLocal() as db:
            run_dedupe(db, limit=5000)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: dedupe crashed: {}", exc)


async def _run_embed() -> None:
    from app.db.session import SessionLocal
    from app.pipeline.embed import run_embed_batch

    try:
        with SessionLocal() as db:
            await run_embed_batch(db, batch_size=64, max_batches=20)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: embed crashed: {}", exc)


async def _run_cluster() -> None:
    from app.db.session import SessionLocal
    from app.pipeline.cluster import run_cluster

    try:
        with SessionLocal() as db:
            run_cluster(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: cluster crashed: {}", exc)


async def _run_extract() -> None:
    from app.analyzer.extract import run_extract
    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            await run_extract(db, max_clusters=10)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: extract crashed: {}", exc)


async def _run_score() -> None:
    from app.db.session import SessionLocal
    from app.scorer import run_score

    try:
        with SessionLocal() as db:
            await run_score(db, limit=30)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: score crashed: {}", exc)


async def _run_brief() -> None:
    from app.db.session import SessionLocal
    from app.report import run_briefs

    try:
        with SessionLocal() as db:
            await run_briefs(db, max_briefs=3)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: brief crashed: {}", exc)


async def _run_weekly() -> None:
    """Generate the weekly issue (idempotent for the day) AND fan out the
    D15 outbound automation: SMTP newsletter + queued tweet.

    Each step is best-effort and isolated so a transient SMTP / X failure
    can't block report generation."""
    from app.db.session import SessionLocal
    from app.notify.newsletter import dispatch_weekly
    from app.notify.twitter import enqueue_weekly_post
    from app.notify.weibo import enqueue_weekly_post as enqueue_weibo_weekly
    from app.report.weekly import generate_weekly

    try:
        with SessionLocal() as db:
            stats = generate_weekly(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: weekly generate crashed: {}", exc)
        return

    # Resolve the freshly-published report (or the last existing one) for
    # downstream fan-out.
    report_id = getattr(stats, "weekly_report_id", None)

    try:
        with SessionLocal() as db:
            from app.models.weekly_report import WeeklyReport
            from sqlalchemy import desc, select
            report = None
            if report_id:
                report = db.get(WeeklyReport, report_id)
            if report is None:
                report = db.scalar(
                    select(WeeklyReport).order_by(desc(WeeklyReport.id)).limit(1)
                )
            if report is None:
                logger.info("scheduler: no weekly report to fan out")
                return
            try:
                enqueue_weekly_post(db, report)
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.warning("scheduler: enqueue tweet failed: {}", exc)
            try:
                enqueue_weibo_weekly(db, report)
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.warning("scheduler: enqueue weibo failed: {}", exc)
            try:
                dispatch_weekly(db, report)
            except Exception as exc:  # noqa: BLE001
                logger.exception("scheduler: dispatch_weekly crashed: {}", exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: weekly fan-out crashed: {}", exc)


async def _run_social_drain() -> None:
    """Drain queued Twitter + Weibo posts. No-op when both providers are off."""
    from app.db.session import SessionLocal
    from app.notify.twitter import post_pending as post_twitter
    from app.notify.weibo import post_pending as post_weibo

    try:
        with SessionLocal() as db:
            post_twitter(db, limit=10)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: twitter drain crashed: {}", exc)
    try:
        with SessionLocal() as db:
            post_weibo(db, limit=10)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: weibo drain crashed: {}", exc)


async def _run_github_sync() -> None:
    """Periodic catch-up: re-push the most-recent briefs in case earlier
    pushes failed (e.g. transient 5xx). Idempotent — GitHub merges via sha."""
    from app.db.session import SessionLocal
    from app.notify.github_sync import sync_recent

    try:
        with SessionLocal() as db:
            sync_recent(db, limit=10)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: github_sync crashed: {}", exc)


async def _run_email_retry() -> None:
    from app.db.session import SessionLocal
    from app.notify.retry import retry_failed

    try:
        with SessionLocal() as db:
            retry_failed(db, limit=200)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: email_retry crashed: {}", exc)


async def _run_expire_redeem() -> None:
    from app.billing.expire import expire_redeem_subs
    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            expire_redeem_subs(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: expire_redeem crashed: {}", exc)


async def _run_admin_digest() -> None:
    from app.db.session import SessionLocal
    from app.notify.admin_digest import send_daily_digest

    try:
        with SessionLocal() as db:
            send_daily_digest(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: admin_digest crashed: {}", exc)


async def _run_cold_start() -> None:
    from app.db.session import SessionLocal
    from app.notify.cold_start import run as run_cold_start

    try:
        with SessionLocal() as db:
            run_cold_start(db)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler: cold_start crashed: {}", exc)


# Track whether we've alerted on today's LLM budget threshold so the worker
# only fires one webhook per breach instead of every 30 minutes.
_LLM_ALERT_DAY: str | None = None
_LLM_ALERT_OVER: str | None = None


async def _run_llm_budget_check() -> None:
    """Watch today's LLM spend; alert once at threshold and once at full cap."""
    from datetime import datetime, timezone

    from app.core import llm_router

    global _LLM_ALERT_DAY, _LLM_ALERT_OVER
    today = datetime.now(tz=timezone.utc).date().isoformat()
    try:
        st = llm_router.budget_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_budget_check failed: {}", exc)
        return
    threshold = float(settings.llm_budget_alert_pct or 0.0)
    if threshold > 0 and st.used_pct >= threshold * 100 and _LLM_ALERT_DAY != today:
        notify_admin(
            f"🪙 LLM budget at {st.used_pct:.0f}% of cap",
            f"Spent ¥{st.spent_cny:.2f} of ¥{st.limit_cny:.2f} today.",
            level="warn",
            key=f"llm_budget_threshold:{today}",
        )
        _LLM_ALERT_DAY = today
    if st.over and _LLM_ALERT_OVER != today:
        notify_admin(
            "🛑 LLM budget exhausted",
            f"Today's spend ¥{st.spent_cny:.2f} hit the cap ¥{st.limit_cny:.2f}. "
            "Pipeline LLM calls will be throttled until UTC midnight.",
            level="error",
            key=f"llm_budget_over:{today}",
        )
        _LLM_ALERT_OVER = today


_PIPELINE_FNS = {
    "dedupe": _run_dedupe,
    "embed": _run_embed,
    "cluster": _run_cluster,
    "extract": _run_extract,
    "score": _run_score,
    "brief": _run_brief,
}


def _instrument(job_id: str, fn):  # type: ignore[no-untyped-def]
    """Wrap an async pipeline coroutine to emit job duration + outcome metrics."""
    async def runner() -> None:
        started = time.perf_counter()
        outcome = "ok"
        err: Exception | None = None
        try:
            await fn()
        except Exception as exc:  # noqa: BLE001
            outcome = "error"
            err = exc
            raise  # already logged inside fn; re-raise so APScheduler marks the run failed
        finally:
            record_job(job_id, outcome, time.perf_counter() - started)
            # D19: alert on failure for high-impact ops jobs.
            if err is not None and job_id in {
                "weekly_generate", "admin_digest", "expire_redeem"
            }:
                notify_admin(
                    f"❌ Scheduled job failed · {job_id}",
                    f"{type(err).__name__}: {err}",
                    level="error",
                    key=f"job_failed:{job_id}",
                    throttle_seconds=1800,
                )
    runner.__name__ = f"instrumented_{job_id}"
    return runner


def start() -> None:
    global _scheduler
    if _is_disabled():
        logger.info("scheduler disabled (env or sqlite)")
        return
    if _scheduler is not None:
        return

    sch = AsyncIOScheduler(timezone="UTC")
    for name, minutes, kwargs in JOB_PLAN:
        sch.add_job(
            _run_collector,
            trigger=IntervalTrigger(minutes=minutes),
            id=f"collect_{name}",
            kwargs={"name": name, **kwargs},
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
            replace_existing=True,
        )
    for name, minutes in PIPELINE_PLAN:
        sch.add_job(
            _instrument(f"pipeline_{name}", _PIPELINE_FNS[name]),
            trigger=IntervalTrigger(minutes=minutes),
            id=f"pipeline_{name}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
            replace_existing=True,
        )
    # Weekly digest cron: every Monday 01:00 UTC (= 09:00 Asia/Shanghai).
    sch.add_job(
        _instrument("weekly_generate", _run_weekly),
        trigger=CronTrigger(day_of_week="mon", hour=1, minute=0, timezone="UTC"),
        id="weekly_generate",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        replace_existing=True,
    )
    # D19: ops automation
    sch.add_job(
        _instrument("email_retry", _run_email_retry),
        trigger=IntervalTrigger(hours=6),
        id="email_retry",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        replace_existing=True,
    )
    sch.add_job(
        _instrument("expire_redeem", _run_expire_redeem),
        trigger=IntervalTrigger(hours=1),
        id="expire_redeem",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        replace_existing=True,
    )
    # Daily admin digest at 00:30 UTC (= 08:30 Asia/Shanghai).
    sch.add_job(
        _instrument("admin_digest", _run_admin_digest),
        trigger=CronTrigger(hour=0, minute=30, timezone="UTC"),
        id="admin_digest",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        replace_existing=True,
    )
    sch.add_job(
        _instrument("cold_start", _run_cold_start),
        trigger=IntervalTrigger(hours=6),
        id="cold_start",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        replace_existing=True,
    )
    sch.add_job(
        _instrument("llm_budget_check", _run_llm_budget_check),
        trigger=IntervalTrigger(minutes=30),
        id="llm_budget_check",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        replace_existing=True,
    )
    # Drain queued social posts every 15m (X + Weibo).
    sch.add_job(
        _instrument("social_drain", _run_social_drain),
        trigger=IntervalTrigger(minutes=15),
        id="social_drain",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        replace_existing=True,
    )
    # Re-push briefs to GitHub hourly to recover from transient failures.
    sch.add_job(
        _instrument("github_sync", _run_github_sync),
        trigger=IntervalTrigger(hours=1),
        id="github_sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        replace_existing=True,
    )

    sch.start()
    _scheduler = sch
    logger.info(
        "scheduler started: {} collectors + {} pipeline jobs + 1 weekly cron + 5 ops jobs",
        len(JOB_PLAN), len(PIPELINE_PLAN),
    )


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler stopped")
