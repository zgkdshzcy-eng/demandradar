"""Admin alerting via a generic webhook (Slack/Discord/Lark/etc.).

All sites that need to surface a real-time signal to the operator import
:func:`notify_admin`. The function is best-effort: any HTTP/transport
failure is logged but never raised, so callers can sprinkle alerts in
exception handlers without worrying about cascading failures.

Empty `ADMIN_WEBHOOK_URL` disables alerts entirely.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import logger

# Per-key rate limiting so we don't spam the channel during incidents.
_LAST_SENT_AT: dict[str, float] = {}
_DEFAULT_THROTTLE_SECONDS = 600  # 10 min


def _format_payload(title: str, body: str, level: str) -> dict[str, Any]:
    """Render to a Slack-compatible payload that Discord also accepts (it
    ignores `attachments` but renders `text`)."""
    color = {
        "info": "#3b82f6",
        "warn": "#f59e0b",
        "error": "#ef4444",
        "success": "#10b981",
    }.get(level, "#6b7280")
    text = f"*[{level.upper()}]* {title}"
    if body:
        text += f"\n{body}"
    return {
        "text": text,
        "attachments": [
            {
                "color": color,
                "fields": [
                    {"title": "title", "value": title, "short": False},
                    {"title": "level", "value": level, "short": True},
                    {"title": "env", "value": settings.app_env, "short": True},
                ],
                "text": body,
            }
        ],
    }


def notify_admin(
    title: str,
    body: str = "",
    *,
    level: str = "info",
    key: str | None = None,
    throttle_seconds: int = _DEFAULT_THROTTLE_SECONDS,
) -> bool:
    """Post one message to the admin webhook. Returns True iff actually sent.

    `key` + `throttle_seconds` collapse repeated alerts (e.g. the same
    failing collector firing every hour). Pass `key=None` to bypass throttling.
    """
    if not settings.admin_webhook_url:
        return False

    if key is not None and throttle_seconds > 0:
        now = time.time()
        last = _LAST_SENT_AT.get(key, 0.0)
        if now - last < throttle_seconds:
            logger.debug("alert throttled key={} title={}", key, title)
            return False
        _LAST_SENT_AT[key] = now

    payload = _format_payload(title, body, level)
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                settings.admin_webhook_url,
                content=json.dumps(payload),
                headers={"content-type": "application/json"},
            )
        if r.status_code >= 300:
            logger.warning(
                "alert webhook returned {}: {}", r.status_code, r.text[:200]
            )
            return False
        logger.info("alert sent: {} ({})", title, level)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("alert webhook failed: {}", exc)
        return False


__all__ = ["notify_admin"]
