"""Loguru-based logging setup.

Two output formats:
- `text` (default, dev-friendly, ANSI colours)
- `json`  (structured, one JSON object per line — for prod log aggregators)

Switch via env `LOG_FORMAT=json`.

Each record carries the contextual `request_id` (when set by the
RequestIdMiddleware) so a single HTTP request can be traced across log lines.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from loguru import logger

from app.core.config import settings


def _json_sink(message) -> None:  # type: ignore[no-untyped-def]
    """Serialise a loguru record into a single-line JSON document."""
    record = message.record
    payload: dict[str, object] = {
        "ts": record["time"].astimezone(timezone.utc).isoformat(),
        "level": record["level"].name,
        "msg": record["message"],
        "logger": record["name"],
        "module": record["module"],
        "line": record["line"],
    }
    extra = record.get("extra") or {}
    if extra:
        # Lift well-known fields and keep the rest under "extra".
        for k in ("request_id", "method", "path", "status", "latency_ms", "ip"):
            if k in extra:
                payload[k] = extra[k]
        leftover = {k: v for k, v in extra.items() if k not in payload}
        if leftover:
            payload["extra"] = leftover
    if record["exception"] is not None:
        payload["exception"] = record["exception"].repr if record["exception"] else None
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def setup_logging() -> None:
    logger.remove()
    level = (
        settings.log_level.upper()
        if settings.log_level
        else ("DEBUG" if settings.is_dev else "INFO")
    )
    if settings.log_format.lower() == "json":
        logger.add(_json_sink, level=level, format="{message}")
    else:
        logger.add(
            sys.stdout,
            level=level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            backtrace=False,
            diagnose=settings.is_dev,
        )


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


__all__ = ["logger", "setup_logging", "now_iso"]
