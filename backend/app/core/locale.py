"""Locale resolution for transactional emails + newsletter rendering.

Single rule: every recipient row stores a `locale` column. When that column
is NULL we fall back to the request `Accept-Language` header (best-effort
parse), and finally to ``DEFAULT_LOCALE`` (English post-pivot).

Used by:
- ``api/auth.py`` and ``api/waitlist.py`` on first signup to persist the
  client's preferred locale.
- ``billing/webhook.py`` to render `paid_confirmation` / `referral_bonus`.
- ``notify/newsletter.py`` to pick per-recipient template variants.
"""
from __future__ import annotations

import re
from typing import Iterable

DEFAULT_LOCALE = "en"
SUPPORTED: tuple[str, ...] = ("en", "zh")

# `zh-CN, zh;q=0.9, en;q=0.8`  ->  [("zh-CN", 1.0), ("zh", 0.9), ("en", 0.8)]
_LANG_TAG_RE = re.compile(
    r"\s*([a-zA-Z]{1,8}(?:-[a-zA-Z0-9]{1,8})*)\s*(?:;\s*q\s*=\s*([0-9.]+))?",
)


def _parse_accept_language(header: str) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    for raw in header.split(","):
        raw = raw.strip()
        if not raw:
            continue
        m = _LANG_TAG_RE.match(raw)
        if not m:
            continue
        tag = m.group(1).lower()
        q_raw = m.group(2)
        try:
            q = float(q_raw) if q_raw is not None else 1.0
        except ValueError:
            q = 1.0
        pairs.append((tag, q))
    pairs.sort(key=lambda p: p[1], reverse=True)
    return pairs


def _normalise(tag: str) -> str | None:
    """Reduce a BCP47 tag like `zh-CN` to a supported locale (`zh`).
    Returns None when the language family isn't supported."""
    if not tag:
        return None
    primary = tag.split("-", 1)[0].lower()
    if primary in SUPPORTED:
        return primary
    return None


def from_accept_language(header: str | None) -> str | None:
    """Pick the best supported locale from an Accept-Language header, or
    None if nothing matches."""
    if not header:
        return None
    for tag, _q in _parse_accept_language(header):
        norm = _normalise(tag)
        if norm:
            return norm
    return None


def pick_locale(
    *,
    explicit: str | None = None,
    header: str | None = None,
    fallback: str = DEFAULT_LOCALE,
) -> str:
    """Resolution order: explicit hint -> Accept-Language -> fallback.

    The hint is what the frontend may pass in the request body (it has
    access to the locale cookie). If callers pass an unsupported value we
    drop down to the next strategy rather than echo it back."""
    if explicit:
        norm = _normalise(explicit)
        if norm:
            return norm
    sniffed = from_accept_language(header)
    if sniffed:
        return sniffed
    return fallback if fallback in SUPPORTED else DEFAULT_LOCALE


def stored_or(default: str, stored: str | None) -> str:
    """Helper for the email side: if the user row has a stored locale use it,
    otherwise fall back to ``default``. Always returns a supported locale."""
    if stored and stored in SUPPORTED:
        return stored
    return default if default in SUPPORTED else DEFAULT_LOCALE


def for_each(emails: Iterable[str], lookup: dict[str, str | None]) -> dict[str, str]:
    """Build an `email -> locale` map, defaulting missing/null lookups."""
    return {e: stored_or(DEFAULT_LOCALE, lookup.get(e)) for e in emails}


__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED",
    "for_each",
    "from_accept_language",
    "pick_locale",
    "stored_or",
]
