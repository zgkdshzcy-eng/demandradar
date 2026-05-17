"""Retry transient SMTP failures recorded in `email_dispatches`.

The newsletter dispatcher persists per-recipient outcomes (D15). When a
provider has a hiccup we end up with `status='failed'` rows. This worker
re-renders and re-sends them up to `MAX_ATTEMPTS` times.

Designed to be idempotent and bounded: if SMTP is still down the next
sweep just bumps `attempts` again and stops once the cap is hit.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.locale import stored_or
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.models.email_dispatch import EmailDispatch
from app.models.user import User
from app.models.waitlist import WaitlistEntry
from app.models.weekly_report import WeeklyReport

MAX_ATTEMPTS = 3
# Don't retry rows newer than this — the original dispatcher might still be
# running and will pick them up on its own pass.
COOLDOWN_MINUTES = 30


@dataclass
class RetryStats:
    candidates: int = 0
    sent: int = 0
    failed: int = 0
    exhausted: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _resolve_locale(db: Session, row: EmailDispatch) -> str:
    if row.user_id:
        u = db.get(User, row.user_id)
        if u and u.locale:
            return stored_or("en", u.locale)
    w = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == row.email))
    if w and w.locale:
        return stored_or("en", w.locale)
    return "en"


def _kind(db: Session, row: EmailDispatch) -> str:
    if row.user_id:
        return "user"
    return "wait"


def retry_failed(db: Session, *, limit: int = 200) -> RetryStats:
    """Resend rows where status='failed' and attempts < MAX_ATTEMPTS."""
    stats = RetryStats()
    if not smtp_enabled():
        return stats

    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=COOLDOWN_MINUTES)
    rows: list[EmailDispatch] = list(
        db.execute(
            select(EmailDispatch)
            .where(EmailDispatch.status == "failed")
            .where(EmailDispatch.attempts < MAX_ATTEMPTS)
            .where(EmailDispatch.updated_at <= cutoff)
            .order_by(EmailDispatch.updated_at.asc())
            .limit(limit)
        ).scalars()
    )
    stats.candidates = len(rows)
    if not rows:
        return stats

    # Lazy import to avoid scheduler module cycle.
    from app.notify.newsletter import _render

    for row in rows:
        report: WeeklyReport | None = None
        if row.weekly_report_id:
            report = db.get(WeeklyReport, row.weekly_report_id)
        if report is None:
            # Without the source report we can't re-render; mark exhausted.
            row.attempts = MAX_ATTEMPTS
            row.error = "weekly report missing"
            stats.exhausted += 1
            continue

        locale = _resolve_locale(db, row)
        kind = _kind(db, row)
        try:
            subject, text, html = _render(
                report=report, email=row.email, kind=kind, locale=locale
            )
        except Exception as exc:  # noqa: BLE001
            row.attempts += 1
            row.error = f"render error: {exc}"[:500]
            stats.failed += 1
            continue

        ok = send_email(to=row.email, subject=subject, text=text, html=html)
        row.attempts += 1
        if ok:
            row.status = "sent"
            row.sent_at = datetime.now(tz=timezone.utc)
            row.error = None
            stats.sent += 1
        else:
            row.error = "smtp retry failed"
            if row.attempts >= MAX_ATTEMPTS:
                stats.exhausted += 1
            else:
                stats.failed += 1

    db.commit()
    logger.info("email retry: {}", stats.as_dict())
    return stats


__all__ = ["MAX_ATTEMPTS", "RetryStats", "retry_failed"]
