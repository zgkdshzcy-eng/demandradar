"""Detect trending painpoints: compare this week's signal count vs last week.
When a painpoint's signal count grows >50% WoW, notify subscribed users.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal
from app.models.trend_alert import TrendAlert
from app.models.user import User

SPIKE_THRESHOLD = 1.5  # 50% growth
MIN_BASELINE = 3  # at least 3 signals last week to qualify


@dataclass
class TrendHit:
    pain_point_id: int
    pain: str
    total_score: float | None
    this_week: int
    last_week: int
    growth_pct: float


def detect_trends(db: Session) -> list[TrendHit]:
    """Find painpoints with >50% WoW signal growth."""
    now = datetime.now(tz=timezone.utc)
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    hits: list[TrendHit] = []

    rows = list(
        db.execute(
            select(PainPoint).where(PainPoint.total_score.is_not(None))
        ).scalars()
    )

    for pp in rows:
        signal_ids = pp.source_signal_ids or []
        if not signal_ids:
            continue

        this_week = db.scalar(
            select(func.count()).select_from(RawSignal).where(
                RawSignal.id.in_(signal_ids),
                RawSignal.collected_at >= this_week_start,
            )
        ) or 0

        last_week = db.scalar(
            select(func.count()).select_from(RawSignal).where(
                RawSignal.id.in_(signal_ids),
                RawSignal.collected_at >= last_week_start,
                RawSignal.collected_at < this_week_start,
            )
        ) or 0

        if last_week < MIN_BASELINE:
            continue
        if this_week <= last_week:
            continue

        growth = this_week / last_week
        if growth >= SPIKE_THRESHOLD:
            hits.append(TrendHit(
                pain_point_id=pp.id,
                pain=pp.pain,
                total_score=float(pp.total_score) if pp.total_score else None,
                this_week=this_week,
                last_week=last_week,
                growth_pct=round((growth - 1) * 100, 1),
            ))

    hits.sort(key=lambda h: h.growth_pct, reverse=True)
    return hits


def dispatch_trend_alerts(db: Session) -> int:
    """Match trending painpoints against user alert subscriptions and send emails."""
    if not smtp_enabled():
        logger.info("trend_alerts: SMTP disabled, skipping")
        return 0

    trends = detect_trends(db)
    if not trends:
        logger.info("trend_alerts: no trending painpoints detected")
        return 0

    alerts = list(
        db.execute(
            select(TrendAlert).where(TrendAlert.active == True)  # noqa: E712
        ).scalars()
    )

    sent = 0
    base_url = settings.public_base_url.rstrip("/")

    for alert in alerts:
        keyword_lower = alert.keyword.lower()
        matching = [
            t for t in trends
            if keyword_lower in t.pain.lower() and (t.total_score or 0) >= alert.min_score
        ]
        if not matching:
            continue

        user = db.get(User, alert.user_id)
        if user is None:
            continue

        top = matching[:3]
        lines = [f"关键词「{alert.keyword}」相关痛点本周信号量激增：\n"]
        for t in top:
            lines.append(
                f"• {t.pain} (评分 {t.total_score or 0:.0f}) "
                f"— 本周 {t.this_week} 条 vs 上周 {t.last_week} 条 (+{t.growth_pct}%)"
            )
        lines.append(f"\n查看完整分析：{base_url}/radar")

        try:
            send_email(
                to=user.email,
                subject=f"📈 趋势预警：{alert.keyword} 相关痛点信号激增",
                text="\n".join(lines),
                html="<br>".join(lines).replace("\n", "<br>"),
            )
            sent += 1
        except Exception as exc:
            logger.warning("trend_alert email failed user={}: {}", user.id, exc)

    logger.info("trend_alerts: sent {} emails for {} trends", sent, len(trends))
    return sent
