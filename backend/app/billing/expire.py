"""Sweep expired redeem-code subscriptions.

Stripe subscriptions self-update via webhook (`customer.subscription.deleted`),
but redeem-code rows have no upstream callback. This sweeper marks them as
``expired`` once `expires_at < now()`, so the entitlement layer immediately
revokes access without the user noticing a stale "active" badge.

Idempotent: re-running on the same dataset is a no-op.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.subscription import Subscription


@dataclass
class ExpireStats:
    scanned: int = 0
    expired: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def expire_redeem_subs(db: Session) -> ExpireStats:
    """Mark all active redeem subs whose `expires_at` is in the past as expired."""
    stats = ExpireStats()
    now = datetime.now(tz=timezone.utc)

    rows: list[Subscription] = list(
        db.execute(
            select(Subscription)
            .where(Subscription.provider == "redeem")
            .where(Subscription.status == "active")
            .where(Subscription.expires_at.is_not(None))
            .where(Subscription.expires_at < now)
        ).scalars()
    )
    stats.scanned = len(rows)
    if not rows:
        return stats

    for sub in rows:
        sub.status = "expired"
        stats.expired += 1
    db.commit()
    logger.info("redeem expire sweep: {}", stats.as_dict())
    return stats


__all__ = ["ExpireStats", "expire_redeem_subs"]
