"""Stateless unsubscribe tokens.

We don't want to keep a separate "unsubscribe codes" table — instead we sign
the email + a short kind tag with HMAC-SHA256 keyed by APP_SECRET_KEY.

Token format: <b64url(email)>.<b64url(kind)>.<b64url(sig[:24])>

- Replay-safe enough: the resulting action is idempotent (sets
  `unsubscribed_at`).
- Forge-resistant: requires the server key.
- No expiry: keep links live forever; the user might revisit a year-old email.

`kind` is "user" (registered users) or "wait" (waitlist entries).
"""
from __future__ import annotations

import base64
import hmac
import hashlib

from app.core.config import settings


_KINDS = {"user", "wait"}


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(email: str, kind: str) -> bytes:
    msg = f"{email}|{kind}".encode("utf-8")
    return hmac.new(
        settings.app_secret_key.encode("utf-8"), msg, hashlib.sha256
    ).digest()


def make_token(email: str, kind: str) -> str:
    """Produce a stateless unsubscribe token for `email` + `kind`."""
    if kind not in _KINDS:
        raise ValueError(f"unknown kind: {kind}")
    sig = _sign(email.lower(), kind)[:24]
    return ".".join(
        [_b64(email.lower().encode("utf-8")), _b64(kind.encode("utf-8")), _b64(sig)]
    )


def verify_token(token: str) -> tuple[str, str] | None:
    """Returns `(email, kind)` if the token is valid, else None."""
    try:
        e_b64, k_b64, sig_b64 = token.split(".")
        email = _b64d(e_b64).decode("utf-8")
        kind = _b64d(k_b64).decode("utf-8")
        sig = _b64d(sig_b64)
    except Exception:  # noqa: BLE001
        return None
    if kind not in _KINDS:
        return None
    expected = _sign(email, kind)[:24]
    if not hmac.compare_digest(expected, sig):
        return None
    return email, kind


def unsubscribe_url(base_url: str, email: str, kind: str) -> str:
    base = base_url.rstrip("/") or "https://demandradar.example.com"
    tok = make_token(email, kind)
    return f"{base}/api/newsletter/unsubscribe?token={tok}"


__all__ = ["make_token", "verify_token", "unsubscribe_url"]
