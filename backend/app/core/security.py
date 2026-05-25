"""Stateless tokens used by auth & billing.

We avoid pulling in an extra JWT lib by hand-rolling HS256 with stdlib
`hmac` + `hashlib`. The token format is the standard 3-segment JWT so
existing tooling (jwt.io, browser inspectors) still parses it.

Two distinct token kinds share this primitive:
- session JWT (for logged-in users)
- redeem code (offline-issued payload that grants a subscription on /api/billing/redeem)

Both bind to APP_SECRET_KEY so rotating the key invalidates everything.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings


# ---------- low-level helpers ----------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign(message: bytes, key: str) -> bytes:
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).digest()


def _now_ts() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


# ---------- generic JWT (HS256) ----------

class TokenError(Exception):
    """Raised on any verification failure (bad sig, expired, malformed)."""


def encode_jwt(payload: dict[str, Any], *, key: str | None = None) -> str:
    """Encode a JWT-style HS256 token. Caller is responsible for setting `exp`."""
    key = key or settings.app_secret_key
    if not key:
        raise TokenError("APP_SECRET_KEY is not configured; cannot sign tokens")
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = _b64url_encode(_sign(signing_input, key))
    return f"{h_b64}.{p_b64}.{sig}"


def decode_jwt(token: str, *, key: str | None = None) -> dict[str, Any]:
    """Decode + verify. Raises TokenError on any failure."""
    key = key or settings.app_secret_key
    if not key:
        raise TokenError("APP_SECRET_KEY is not configured; cannot verify tokens")
    try:
        h_b64, p_b64, sig_b64 = token.split(".")
    except ValueError as e:
        raise TokenError("malformed token") from e

    expected = _b64url_encode(_sign(f"{h_b64}.{p_b64}".encode("ascii"), key))
    if not hmac.compare_digest(expected, sig_b64):
        raise TokenError("bad signature")

    try:
        payload = json.loads(_b64url_decode(p_b64))
    except Exception as e:  # noqa: BLE001
        raise TokenError("bad payload") from e

    exp = payload.get("exp")
    if exp is not None and _now_ts() > int(exp):
        raise TokenError("expired")
    return payload


# ---------- session token ----------

def issue_session_token(user_id: int, email: str, *, ttl_days: int = 30) -> str:
    """Long-lived session JWT placed in an HttpOnly cookie."""
    now = _now_ts()
    return encode_jwt(
        {
            "sub": str(user_id),
            "email": email,
            "iat": now,
            "exp": now + ttl_days * 86400,
            "kind": "session",
        }
    )


def issue_magic_link_token(
    email: str,
    *,
    ttl_minutes: int = 15,
    ref: str | None = None,
) -> str:
    """Short-lived magic-link token for email verification.

    `ref` carries a D13 referral code so it survives the email round-trip.
    """
    now = _now_ts()
    payload: dict[str, Any] = {
        "email": email,
        "iat": now,
        "exp": now + ttl_minutes * 60,
        "kind": "magic",
        "nonce": secrets.token_hex(8),
    }
    if ref:
        payload["ref"] = ref
    return encode_jwt(payload)


# ---------- redeem code ----------

VALID_PLANS = {"weekly_pro", "brief_oneoff", "studio"}


def issue_redeem_code(
    plan: str,
    *,
    days: int = 30,
    brief_id: int | None = None,
    note: str = "",
) -> str:
    """Generate an offline redeem code that, when posted to /api/billing/redeem,
    grants the caller a subscription. Issued via CLI by the admin.

    For `brief_oneoff` the code is bound to a specific brief id.
    """
    if plan not in VALID_PLANS:
        raise ValueError(f"invalid plan: {plan}")
    now = _now_ts()
    payload: dict[str, Any] = {
        "kind": "redeem",
        "plan": plan,
        "days": days,
        "iat": now,
        "exp": now + 365 * 86400,  # code itself expires after 1 year
        "nonce": secrets.token_hex(6),
    }
    if brief_id is not None:
        payload["brief_id"] = brief_id
    if note:
        payload["note"] = note[:80]
    return encode_jwt(payload)


def parse_redeem_code(code: str) -> dict[str, Any]:
    """Verify + return the redeem payload. Raises TokenError on failure."""
    payload = decode_jwt(code)
    if payload.get("kind") != "redeem":
        raise TokenError("not a redeem code")
    if payload.get("plan") not in VALID_PLANS:
        raise TokenError("unknown plan")
    return payload


# ---------- helpers for entitlement bookkeeping ----------

def subscription_expiry(days: int) -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(days=days)
