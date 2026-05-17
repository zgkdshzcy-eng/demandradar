"""Cold-start re-engagement: nudge users who signed up but haven't paid.

Eligibility:
- account is older than COLD_START_WINDOW_HOURS but younger than +24h
  (so we don't keep emailing the same user forever)
- no active or past subscriptions
- not unsubscribed
- never received a `cold_start` campaign email before (idempotency via
  `email_dispatches.campaign='cold_start'`)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email_templates import cold_start_top3
from app.core.locale import stored_or
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.models.email_dispatch import EmailDispatch
from app.models.pain_point import PainPoint
from app.models.subscription import Subscription
from app.models.user import User

CAMPAIGN = "cold_start"


@dataclass
class ColdStartStats:
    candidates: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _eligible_users(db: Session) -> list[User]:
    """Find users to nudge in this run."""
    now = datetime.now(tz=timezone.utc)
    window_start = now - timedelta(hours=settings.cold_start_window_hours + 24)
    window_end = now - timedelta(hours=settings.cold_start_window_hours)

    # Subquery: users who already have a subscription (any status).
    sub_users = select(Subscription.user_id).distinct()
    # Subquery: users we already cold-started.
    already_sent = (
        select(EmailDispatch.user_id)
        .where(EmailDispatch.campaign == CAMPAIGN)
        .where(EmailDispatch.user_id.is_not(None))
    )

    rows = list(
        db.execute(
            select(User)
            .where(User.created_at >= window_start)
            .where(User.created_at <= window_end)
            .where(User.unsubscribed_at.is_(None))
            .where(User.is_active.is_(True))
            .where(User.id.not_in(sub_users))
            .where(User.id.not_in(already_sent))
            .order_by(User.id)
            .limit(200)
        ).scalars()
    )
    return rows


def _top_painpoints(db: Session, *, limit: int = 3) -> list[dict]:
    rows: list[PainPoint] = list(
        db.execute(
            select(PainPoint)
            .where(PainPoint.total_score.is_not(None))
            .where(PainPoint.go_no_go == "go")
            .order_by(desc(PainPoint.total_score))
            .limit(limit)
        ).scalars()
    )
    return [
        {
            "pain_point_id": pp.id,
            "pain": pp.pain,
            "target_user": pp.target_user,
            "score": float(pp.total_score or 0.0),
        }
        for pp in rows
    ]


def run(db: Session, *, dry_run: bool = False) -> ColdStartStats:
    """Send the cold-start email to all eligible users in one pass."""
    stats = ColdStartStats()
    if not smtp_enabled() and not dry_run:
        return stats

    items = _top_painpoints(db)
    if not items:
        logger.info("cold_start: no painpoints to feature; skipping")
        return stats

    users = _eligible_users(db)
    stats.candidates = len(users)
    if not users:
        return stats

    for user in users:
        locale = stored_or("en", user.locale)
        try:
            subj, txt, html = cold_start_top3(
                user.email, items=items, locale=locale
            )
        except Exception as exc:  # noqa: BLE001
            stats.failed += 1
            logger.warning("cold_start render failed user={}: {}", user.id, exc)
            continue

        if dry_run:
            stats.sent += 1
            continue

        ok = send_email(to=user.email, subject=subj, text=txt, html=html)
        now = datetime.now(tz=timezone.utc)
        row = EmailDispatch(
            campaign=CAMPAIGN,
            email=user.email,
            user_id=user.id,
            status="sent" if ok else "failed",
            attempts=1,
            sent_at=now if ok else None,
            error=None if ok else "smtp send returned False",
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            stats.skipped += 1
            continue
        if ok:
            stats.sent += 1
        else:
            stats.failed += 1

    db.commit()
    logger.info("cold_start: {}", stats.as_dict())
    return stats


__all__ = ["CAMPAIGN", "ColdStartStats", "run"]
