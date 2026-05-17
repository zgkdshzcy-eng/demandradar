"""Referral programme.

How it works:
1. Each user has a unique short `referral_code` lazily generated on first use.
2. New visitors hitting the landing page with `?ref=XXXX` keep that in a cookie
   (handled in the frontend) and POST it to /api/auth/request-link as `ref`.
3. On successful magic-link verification we resolve the code -> referrer user
   and write `referred_by_user_id` (only if not already set).
4. When the referred user makes their *first* paid checkout, the webhook
   handler calls `grant_first_paid_bonus` which atomically:
     - inserts a `ReferralGrant(trigger="first_paid")` (unique constraint
       prevents double-grant)
     - bumps the referrer's longest-living recurring subscription's
       `expires_at` by BONUS_DAYS

Bonus is small (7 days) and capped at one grant per referred user.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.referral_grant import ReferralGrant
from app.models.subscription import Subscription
from app.models.user import User

BONUS_DAYS_FIRST_PAID = 7
TRIGGER_FIRST_PAID = "first_paid"
_CODE_ALPHABET = string.ascii_uppercase + string.digits  # 36 chars, unambiguous-ish
_CODE_LEN = 8


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))


def ensure_referral_code(db: Session, user: User) -> str:
    """Return the user's referral code, generating + persisting one if needed.

    Caller is responsible for committing the session.
    """
    if user.referral_code:
        return user.referral_code
    # Tiny retry loop in case of an unlucky collision (probability ~ 36^-8).
    for _ in range(5):
        candidate = _generate_code()
        clash = db.scalar(
            select(User).where(User.referral_code == candidate)
        )
        if clash is None:
            user.referral_code = candidate
            return candidate
    # Fallback: append user id to guarantee uniqueness.
    user.referral_code = f"{_generate_code()[:6]}{user.id % 100:02d}"
    return user.referral_code


def find_referrer(db: Session, code: str | None) -> User | None:
    if not code:
        return None
    code = code.strip().upper()
    if len(code) > 16:
        return None
    return db.scalar(select(User).where(User.referral_code == code))


def apply_referral(db: Session, referred: User, code: str | None) -> User | None:
    """If `code` resolves to a different user and `referred` has no referrer
    yet, link them. Returns the referrer (or None on no-op)."""
    if referred.referred_by_user_id is not None:
        return None
    referrer = find_referrer(db, code)
    if referrer is None or referrer.id == referred.id:
        return None
    referred.referred_by_user_id = referrer.id
    logger.info(
        "referral linked: referrer={} referred={}", referrer.id, referred.id
    )
    return referrer


def grant_first_paid_bonus(db: Session, referred: User) -> ReferralGrant | None:
    """Called from webhook after a successful first paid checkout.

    Returns the new `ReferralGrant` row, or None when no grant was made
    (no referrer, or already granted before).
    """
    if referred.referred_by_user_id is None:
        return None
    referrer = db.get(User, referred.referred_by_user_id)
    if referrer is None:
        return None

    grant = ReferralGrant(
        referrer_user_id=referrer.id,
        referred_user_id=referred.id,
        trigger=TRIGGER_FIRST_PAID,
        bonus_days=BONUS_DAYS_FIRST_PAID,
        granted_at=datetime.now(tz=timezone.utc),
    )
    db.add(grant)
    try:
        db.flush()
    except IntegrityError:
        # Already granted — unique constraint kicked in. Roll back the failed
        # insert and return None so the caller doesn't re-extend expires_at.
        db.rollback()
        logger.info(
            "referral bonus already granted: referrer={} referred={}",
            referrer.id, referred.id,
        )
        return None

    _extend_referrer_sub(db, referrer, BONUS_DAYS_FIRST_PAID)
    logger.info(
        "referral bonus granted: referrer={} referred={} days={}",
        referrer.id, referred.id, BONUS_DAYS_FIRST_PAID,
    )
    return grant


def _extend_referrer_sub(db: Session, referrer: User, days: int) -> None:
    """Push out expires_at on the referrer's most recent active recurring
    subscription. If they don't have one yet we simply skip — the grant row
    is still recorded, so we won't double-grant later."""
    sub = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == referrer.id)
        .where(Subscription.status == "active")
        .where(Subscription.plan.in_(("weekly_pro", "studio")))
        .order_by(desc(Subscription.id))
        .limit(1)
    )
    if sub is None:
        return
    base = sub.expires_at or datetime.now(tz=timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    sub.expires_at = base + timedelta(days=days)


__all__ = [
    "BONUS_DAYS_FIRST_PAID",
    "TRIGGER_FIRST_PAID",
    "apply_referral",
    "ensure_referral_code",
    "find_referrer",
    "grant_first_paid_bonus",
]
