"""Notify (SMTP) tests - SMTP is not configured in tests, so functions no-op."""
from __future__ import annotations

from app.core.notify import send_bulk, send_email, smtp_enabled


def test_smtp_disabled_by_default() -> None:
    assert smtp_enabled() is False


def test_send_email_returns_false_when_disabled() -> None:
    ok = send_email(to="x@example.com", subject="t", text="hi")
    assert ok is False


def test_send_bulk_counts_failures() -> None:
    stats = send_bulk(["a@x.com", "b@x.com"], subject="t", text="hi")
    assert stats.attempted == 2
    assert stats.sent == 0
    assert stats.failed == 2
