"""Weekly newsletter dispatcher.

Pipeline:
1. Resolve recipients = (active users not unsubscribed) ∪
                       (waitlist entries not unsubscribed)
2. For each recipient, upsert an `email_dispatches` row keyed by
   (campaign, email). Skip if a `sent` row already exists.
3. Render the email (HTML + text) with a per-recipient unsubscribe link, send
   via SMTP, then mark the row sent / failed.

Idempotent — calling `dispatch_weekly(report)` twice does not double-send.
Throttled by `NEWSLETTER_DISPATCH_PER_MINUTE` to play nice with shared SMTP
relays.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.locale import stored_or
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.core.unsubscribe import unsubscribe_url
from app.models.email_dispatch import EmailDispatch
from app.models.user import User
from app.models.waitlist import WaitlistEntry
from app.models.weekly_report import WeeklyReport


@dataclass
class DispatchStats:
    campaign: str
    candidates: int = 0
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    smtp_disabled: bool = False

    def as_dict(self) -> dict:
        return self.__dict__.copy()


# ---------- recipient resolution ----------

def _recipients(db: Session) -> list[tuple[str, str, int | None, str]]:
    """Return ``(email, kind, user_id, locale)`` tuples. ``kind`` is
    ``"user"`` or ``"wait"``. Users always win when an email exists in both
    tables. ``locale`` is always a supported value (``"en"`` default)."""
    out: dict[str, tuple[str, str, int | None, str]] = {}

    users = db.execute(
        select(User.email, User.id, User.locale)
        .where(User.is_active.is_(True))
        .where(User.unsubscribed_at.is_(None))
    ).all()
    for email, uid, loc in users:
        e = email.lower()
        out[e] = (e, "user", int(uid), stored_or("en", loc))

    waitlist = db.execute(
        select(WaitlistEntry.email, WaitlistEntry.locale)
        .where(WaitlistEntry.unsubscribed_at.is_(None))
    ).all()
    for email, loc in waitlist:
        e = email.lower()
        out.setdefault(e, (e, "wait", None, stored_or("en", loc)))

    return list(out.values())


# ---------- email rendering ----------

def _default_title(issue: int, locale: str) -> str:
    if locale == "zh":
        return f"DemandRadar 周报 #{issue}"
    return f"DemandRadar weekly #{issue}"


def _render(
    *,
    report: WeeklyReport,
    email: str,
    kind: str,
    locale: str = "en",
) -> tuple[str, str, str]:
    base = settings.public_base_url.rstrip("/") or "https://demandradar.example.com"
    issue = report.issue_no
    issue_url = f"{base}/sample"
    full_url = f"{base}/sample"
    unsub = unsubscribe_url(base, email, kind)
    title = report.title or _default_title(issue, locale)
    teaser = (report.markdown_preview or "").splitlines()[:6]
    teaser_text = "\n".join(teaser)

    subject = f"[DemandRadar] {title}"

    if locale == "zh":
        text = (
            f"{title}\n"
            f"{'=' * len(title)}\n\n"
            f"{teaser_text}\n\n"
            f"--\n"
            f"在线阅读样刊：{full_url}\n"
            f"订阅完整周报：{base}/pricing\n"
            f"取消订阅：{unsub}\n"
        )
        html_lang = "zh-CN"
        eyebrow = (
            f"期号 #{issue} · 自动扫描 9+ 公开数据源 · Top 痛点速览"
        )
        cta_full = "阅读完整样刊"
        cta_pro = "订阅 Pro 周报"
        unsub_label = "不再接收"
        receive_note = "你收到这封邮件，是因为在 DemandRadar 留下了邮箱。"
    else:
        text = (
            f"{title}\n"
            f"{'=' * len(title)}\n\n"
            f"{teaser_text}\n\n"
            f"--\n"
            f"Read the sample issue online: {full_url}\n"
            f"Subscribe to Pro for the full weekly: {base}/pricing\n"
            f"Unsubscribe: {unsub}\n"
        )
        html_lang = "en"
        eyebrow = (
            f"Issue #{issue} · scanned 9+ public sources · Top pain-point digest"
        )
        cta_full = "Read the full sample"
        cta_pro = "Subscribe to Pro"
        unsub_label = "Unsubscribe"
        receive_note = (
            "You're receiving this because you signed up at DemandRadar."
        )

    html = f"""<!doctype html><html lang="{html_lang}"><head><meta charset="utf-8">
<title>{title}</title></head>
<body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;background:#f6f7fb;padding:24px;color:#111;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;padding:28px 32px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
<h1 style="font-size:22px;margin-top:0">{title}</h1>
<p style="color:#666;font-size:13px;margin-top:-6px">{eyebrow}</p>
<pre style="white-space:pre-wrap;font-family:inherit;font-size:14px;line-height:1.65;background:#f9fafb;padding:14px 16px;border-radius:8px;">{teaser_text}</pre>
<p style="margin-top:18px;">
  <a href="{issue_url}" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;">{cta_full}</a>
  &nbsp;
  <a href="{base}/pricing" style="color:#3b82f6;">{cta_pro}</a>
</p>
<hr style="border:0;border-top:1px solid #eee;margin:28px 0 14px;">
<p style="font-size:11px;color:#999;line-height:1.6;">
  {receive_note}<br>
  {unsub_label}: <a href="{unsub}" style="color:#999;">{unsub}</a>
</p>
</div></body></html>"""
    return subject, text, html


# ---------- main entry ----------

def dispatch_weekly(
    db: Session,
    report: WeeklyReport,
    *,
    dry_run: bool = False,
    max_send: int | None = None,
) -> DispatchStats:
    campaign = f"weekly:{report.issue_no}"
    stats = DispatchStats(campaign=campaign)

    if not smtp_enabled() and not dry_run:
        stats.smtp_disabled = True
        logger.info("dispatch_weekly: smtp disabled, returning empty stats")
        return stats

    recipients = _recipients(db)
    stats.candidates = len(recipients)

    cap = max_send if max_send is not None else settings.newsletter_max_per_run
    per_minute = max(1, settings.newsletter_dispatch_per_minute)
    sleep_per = 60.0 / per_minute if per_minute < 600 else 0.0

    sent_in_run = 0
    for email, kind, user_id, locale in recipients:
        if sent_in_run >= cap:
            logger.info(
                "dispatch_weekly: hit per-run cap {} for campaign {}",
                cap, campaign,
            )
            break

        # Idempotency: skip if a `sent` row already exists.
        existing = db.scalar(
            select(EmailDispatch).where(
                EmailDispatch.campaign == campaign,
                EmailDispatch.email == email,
            )
        )
        if existing is not None and existing.status == "sent":
            stats.skipped += 1
            continue

        if dry_run:
            stats.sent += 1
            sent_in_run += 1
            continue

        subject, text, html = _render(
            report=report, email=email, kind=kind, locale=locale
        )
        ok = send_email(to=email, subject=subject, text=text, html=html)

        now = datetime.now(tz=timezone.utc)
        if existing is None:
            row = EmailDispatch(
                campaign=campaign,
                email=email,
                user_id=user_id,
                weekly_report_id=report.id,
                status="sent" if ok else "failed",
                sent_at=now if ok else None,
                attempts=1,
                error=None if ok else "smtp send returned False",
            )
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                # Lost the race — another worker just inserted; treat as skipped.
                stats.skipped += 1
                continue
        else:
            existing.attempts += 1
            existing.status = "sent" if ok else "failed"
            existing.sent_at = now if ok else existing.sent_at
            existing.error = None if ok else "retry failed"

        if ok:
            stats.sent += 1
        else:
            stats.failed += 1

        sent_in_run += 1
        if sleep_per:
            time.sleep(sleep_per)

    db.commit()
    logger.info("dispatch_weekly: {}", stats.as_dict())
    return stats


__all__ = ["DispatchStats", "dispatch_weekly"]
