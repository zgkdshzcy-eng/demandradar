"""Email notifier - Resend API (preferred) or stdlib smtplib.

Resend uses HTTPS (port 443) which works on hosts that block SMTP ports.
Falls back to SMTP when RESEND_API_KEY is not set.

In dev or when neither is configured, calls become no-ops returning False.
"""
from __future__ import annotations

import json
import smtplib
import ssl
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging import logger


@dataclass
class SendStats:
    attempted: int = 0
    sent: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _resend_enabled() -> bool:
    return bool(settings.resend_api_key)


def smtp_enabled() -> bool:
    return _resend_enabled() or bool(settings.smtp_host and settings.smtp_from)


def _send_via_resend(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    """Send email via Resend HTTPS API."""
    payload: dict = {
        "from": settings.smtp_from,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DemandRadar/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status == 200:
                return True
            logger.warning("resend api returned status={}", resp.status)
            return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("resend send failed to={} err={}", to, exc)
        return False


def send_email(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    """Send a single email. Returns True on success, False if disabled / failed."""
    if _resend_enabled():
        return _send_via_resend(to=to, subject=subject, text=text, html=html)

    if not settings.smtp_host or not settings.smtp_from:
        logger.debug("smtp disabled; would send to={} subject={}", to, subject)
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        if settings.smtp_use_tls:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
                s.starttls(context=ctx)
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("smtp send failed to={} err={}", to, exc)
        return False


def send_bulk(
    recipients: list[str],
    *,
    subject: str,
    text: str,
    html: str | None = None,
) -> SendStats:
    """Send the same email to many recipients (sequentially, low rate)."""
    stats = SendStats()
    for r in recipients:
        stats.attempted += 1
        ok = send_email(to=r, subject=subject, text=text, html=html)
        if ok:
            stats.sent += 1
        else:
            stats.failed += 1
    logger.info("bulk send: {}", stats.as_dict())
    return stats
