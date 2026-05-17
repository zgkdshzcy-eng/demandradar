"""Daily admin digest — sent every morning summarising the past 24h."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core import llm_router
from app.core.config import settings
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.models.brief import Brief
from app.models.email_dispatch import EmailDispatch
from app.models.payment_event import PaymentEvent
from app.models.raw_signal import RawSignal
from app.models.social_post import SocialPost
from app.models.subscription import Subscription
from app.models.user import User
from app.models.waitlist import WaitlistEntry


@dataclass
class DigestStats:
    new_users: int = 0
    new_waitlist: int = 0
    new_active_subs: int = 0
    new_briefs: int = 0
    new_signals: int = 0
    failed_emails: int = 0
    failed_events: int = 0
    queued_tweets: int = 0
    llm_spent_cny: float = 0.0
    llm_used_pct: float = 0.0
    cards: list[tuple[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        d = self.__dict__.copy()
        d["cards"] = list(self.cards)
        return d


def _count(db: Session, q) -> int:  # type: ignore[no-untyped-def]
    return int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)


def collect(db: Session, *, since: datetime | None = None) -> DigestStats:
    """Compute the digest. Pure: no I/O outside DB."""
    if since is None:
        since = datetime.now(tz=timezone.utc) - timedelta(hours=24)

    stats = DigestStats()
    stats.new_users = _count(
        db, select(User).where(User.created_at >= since)
    )
    stats.new_waitlist = _count(
        db, select(WaitlistEntry).where(WaitlistEntry.created_at >= since)
    )
    stats.new_active_subs = _count(
        db,
        select(Subscription)
        .where(Subscription.created_at >= since)
        .where(Subscription.status == "active"),
    )
    stats.new_briefs = _count(
        db, select(Brief).where(Brief.created_at >= since)
    )
    stats.new_signals = _count(
        db, select(RawSignal).where(RawSignal.created_at >= since)
    )
    stats.failed_emails = _count(
        db,
        select(EmailDispatch)
        .where(EmailDispatch.updated_at >= since)
        .where(EmailDispatch.status == "failed"),
    )
    stats.failed_events = _count(
        db,
        select(PaymentEvent)
        .where(PaymentEvent.received_at >= since)
        .where(PaymentEvent.type.like("%__failed")),
    )
    stats.queued_tweets = _count(
        db,
        select(SocialPost)
        .where(SocialPost.platform == "x")
        .where(SocialPost.status.in_(("queued", "manual"))),
    )

    budget = llm_router.budget_status()
    stats.llm_spent_cny = round(budget.spent_cny, 2)
    stats.llm_used_pct = round(budget.used_pct, 1)

    stats.cards = [
        ("New users (24h)", str(stats.new_users)),
        ("New waitlist (24h)", str(stats.new_waitlist)),
        ("New active subs (24h)", str(stats.new_active_subs)),
        ("New briefs (24h)", str(stats.new_briefs)),
        ("New raw signals (24h)", f"{stats.new_signals:,}"),
        ("Failed emails (24h)", str(stats.failed_emails)),
        ("Failed payment events (24h)", str(stats.failed_events)),
        ("Pending tweets", str(stats.queued_tweets)),
        (
            "LLM spend today",
            f"¥{stats.llm_spent_cny:.2f} ({stats.llm_used_pct:.0f}% of cap)",
        ),
    ]
    return stats


def _render(stats: DigestStats) -> tuple[str, str, str]:
    base = settings.public_base_url.rstrip("/") or "https://demandradar.example.com"
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    subject = f"[DemandRadar] Daily admin digest · {today}"

    lines = [f"DemandRadar daily digest ({today} UTC)", ""]
    for label, value in stats.cards:
        lines.append(f"- {label}: {value}")
    lines += ["", f"Admin dashboard: {base}/admin"]
    text = "\n".join(lines)

    rows = "".join(
        f"<tr><td style='padding:6px 14px 6px 0;color:#666;'>{label}</td>"
        f"<td style='padding:6px 0;font-weight:600;'>{value}</td></tr>"
        for label, value in stats.cards
    )
    html = (
        "<!doctype html><html><body style='font-family:-apple-system,Segoe UI,"
        "Helvetica,Arial,sans-serif;background:#f6f7fb;padding:24px;color:#111;'>"
        "<div style='max-width:560px;margin:0 auto;background:#fff;"
        "border-radius:12px;padding:24px 28px;box-shadow:0 2px 8px rgba(0,0,0,.04);'>"
        f"<h2 style='margin-top:0'>Daily admin digest · {today}</h2>"
        f"<table style='font-size:14px;'>{rows}</table>"
        f"<p style='margin-top:18px;'><a href='{base}/admin' "
        f"style='display:inline-block;background:#3b82f6;color:#fff;padding:8px 16px;"
        f"border-radius:6px;text-decoration:none;'>Open admin</a></p>"
        "</div></body></html>"
    )
    return subject, text, html


def send_daily_digest(db: Session) -> bool:
    """Compute + email the digest. Returns True on a successful send."""
    if not settings.admin_email or not smtp_enabled():
        logger.debug("admin digest skipped: ADMIN_EMAIL or SMTP missing")
        return False
    stats = collect(db)
    subject, text, html = _render(stats)
    ok = send_email(
        to=settings.admin_email, subject=subject, text=text, html=html
    )
    logger.info("admin digest send ok={} stats={}", ok, stats.as_dict())
    return ok


__all__ = ["DigestStats", "collect", "send_daily_digest"]
