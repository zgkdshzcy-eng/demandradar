"""Public, no-auth statistics endpoint for the homepage and /status page.

Exposes only sanitized aggregates — never per-user data — so we can render
"ZZ users · NN issues · MM briefs" social proof and a public status page
without authentication. Cached for 60 seconds at the application layer to
absorb thundering-herd from the homepage.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core import source_health
from app.db.session import get_session
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal
from app.models.subscription import Subscription
from app.models.user import User
from app.models.weekly_report import WeeklyReport

router = APIRouter(prefix="/api/public", tags=["public"])


# ---------- response schemas ----------


class PublicStats(BaseModel):
    users: int
    subscribers: int
    weekly_issues: int
    briefs: int
    pain_points_scored: int
    signals_scanned: int
    mrr_usd: float
    last_issue_at: datetime | None
    last_brief_at: datetime | None


class SourceStatus(BaseModel):
    name: str
    state: str  # "healthy" | "degraded" | "down"
    consecutive_failures: int
    interval_mult: int
    last_error: str | None


class WeeklyHistory(BaseModel):
    issue_no: int
    title: str
    period_start: datetime
    period_end: datetime
    items: int


class StatusPayload(BaseModel):
    overall: str  # "healthy" | "degraded" | "down"
    api: str
    sources: list[SourceStatus]
    recent_issues: list[WeeklyHistory]
    last_signal_at: datetime | None


# ---------- in-process cache (60s) ----------

_CACHE: dict[str, tuple[float, object]] = {}
_LOCK = Lock()
_TTL = 60.0


def _cache_get(key: str) -> object | None:
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is None:
        return None
    expires, value = hit
    if expires < time.time():
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    with _LOCK:
        _CACHE[key] = (time.time() + _TTL, value)


# ---------- endpoints ----------


@router.get("/stats", response_model=PublicStats)
def public_stats(db: Session = Depends(get_session)) -> PublicStats:
    """Sanitized site KPIs for homepage social proof. Cached 60s."""
    cached = _cache_get("stats")
    if isinstance(cached, PublicStats):
        return cached

    users = db.scalar(select(func.count()).select_from(User)) or 0
    subscribers = (
        db.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.status == "active")
        )
        or 0
    )
    weekly_issues = db.scalar(select(func.count()).select_from(WeeklyReport)) or 0
    briefs = db.scalar(select(func.count()).select_from(Brief)) or 0
    pain_points_scored = (
        db.scalar(
            select(func.count())
            .select_from(PainPoint)
            .where(PainPoint.total_score.is_not(None))
        )
        or 0
    )
    signals_scanned = db.scalar(select(func.count()).select_from(RawSignal)) or 0

    # MRR: sum amount_cents of active subs in USD cents. We exclude one-off
    # brief purchases by filtering the plan name (brief_oneoff is not recurring
    # but is recorded with status='active' too).
    mrr_cents = int(
        db.scalar(
            select(func.coalesce(func.sum(Subscription.amount_cents), 0))
            .where(Subscription.status == "active")
            .where(Subscription.plan != "brief_oneoff")
        )
        or 0
    )

    last_issue_at = db.scalar(
        select(WeeklyReport.created_at).order_by(desc(WeeklyReport.created_at)).limit(1)
    )
    last_brief_at = db.scalar(
        select(Brief.created_at).order_by(desc(Brief.created_at)).limit(1)
    )

    out = PublicStats(
        users=users,
        subscribers=subscribers,
        weekly_issues=weekly_issues,
        briefs=briefs,
        pain_points_scored=pain_points_scored,
        signals_scanned=signals_scanned,
        mrr_usd=round(mrr_cents / 100.0, 2),
        last_issue_at=last_issue_at,
        last_brief_at=last_brief_at,
    )
    _cache_set("stats", out)
    return out


@router.get("/status", response_model=StatusPayload)
def public_status(db: Session = Depends(get_session)) -> StatusPayload:
    """Public status page payload: source health + recent weekly issues.

    `state` is derived from the in-memory `source_health` snapshot and from the
    timestamp of the latest raw signal: when the last signal is older than 24h
    we mark overall as "degraded" even if the in-memory state looks fine
    (worker may have restarted).
    """
    cached = _cache_get("status")
    if isinstance(cached, StatusPayload):
        return cached

    snap = source_health.snapshot()
    sources: list[SourceStatus] = []
    any_failing = False
    for name, st in sorted(snap.items()):
        consecutive = int(st.get("consecutive_failures") or 0)
        mult = int(st.get("interval_mult") or 1)
        last_error = st.get("last_error")
        if consecutive == 0 and mult == 1:
            state = "healthy"
        elif mult <= 2:
            state = "degraded"
            any_failing = True
        else:
            state = "down"
            any_failing = True
        sources.append(
            SourceStatus(
                name=name,
                state=state,
                consecutive_failures=consecutive,
                interval_mult=mult,
                last_error=str(last_error) if last_error else None,
            )
        )

    last_signal_at = db.scalar(
        select(RawSignal.created_at).order_by(desc(RawSignal.created_at)).limit(1)
    )
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    # last_signal_at may be tz-naive from Postgres; coerce before compare.
    if last_signal_at is not None and last_signal_at.tzinfo is None:
        last_signal_at = last_signal_at.replace(tzinfo=timezone.utc)
    if last_signal_at is None or last_signal_at < cutoff:
        any_failing = True

    overall = "healthy" if not any_failing else "degraded"

    rows = list(
        db.execute(
            select(WeeklyReport).order_by(desc(WeeklyReport.issue_no)).limit(8)
        ).scalars()
    )
    recent = [
        WeeklyHistory(
            issue_no=r.issue_no,
            title=r.title,
            period_start=r.period_start,
            period_end=r.period_end,
            items=len(r.pain_point_ids or []),
        )
        for r in rows
    ]

    out = StatusPayload(
        overall=overall,
        api="ok",
        sources=sources,
        recent_issues=recent,
        last_signal_at=last_signal_at,
    )
    _cache_set("status", out)
    return out
