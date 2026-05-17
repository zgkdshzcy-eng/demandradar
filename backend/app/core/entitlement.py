"""Compute what a user is allowed to read.

A single Entitlement instance summarises a user's effective access at the
current point in time, derived from their `subscriptions` rows.

Plan rules (MVP):
- weekly_pro:    can_read_weekly_full, can_read_any_brief
- studio:        can_read_weekly_full, can_read_any_brief, plus annotated as 'studio'
- brief_oneoff:  unlocks one specific brief id (carried in provider_ref="brief:{id}")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import Subscription


@dataclass
class Entitlement:
    user_id: int | None = None
    plans: list[str] = field(default_factory=list)
    can_read_weekly_full: bool = False
    can_read_any_brief: bool = False
    unlocked_brief_ids: set[int] = field(default_factory=set)
    is_admin: bool = False  # short-circuits everything

    def can_read_brief(self, brief_id: int) -> bool:
        return (
            self.is_admin
            or self.can_read_any_brief
            or brief_id in self.unlocked_brief_ids
        )

    def can_read_weekly(self) -> bool:
        return self.is_admin or self.can_read_weekly_full

    def to_dict(self) -> dict[str, object]:
        return {
            "plans": self.plans,
            "can_read_weekly_full": self.can_read_weekly_full,
            "can_read_any_brief": self.can_read_any_brief,
            "unlocked_brief_ids": sorted(self.unlocked_brief_ids),
            "is_admin": self.is_admin,
        }


ANON = Entitlement()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _coerce_aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d


def compute_entitlement(db: Session, user) -> Entitlement:
    """Build an Entitlement for the given User row (or None for anonymous)."""
    if user is None:
        return Entitlement()

    ent = Entitlement(user_id=user.id, is_admin=bool(getattr(user, "is_admin", False)))

    rows = list(
        db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .where(Subscription.status == "active")
        ).scalars()
    )

    now = _now()
    for sub in rows:
        exp = _coerce_aware(sub.expires_at)
        if exp is not None and exp < now:
            continue  # silently ignore expired (cron can flip them later)
        plan = sub.plan
        ent.plans.append(plan)
        if plan in ("weekly_pro", "studio"):
            ent.can_read_weekly_full = True
            ent.can_read_any_brief = True
        elif plan == "brief_oneoff":
            # D12: prefer the dedicated `brief_id` column; fall back to the
            # legacy provider_ref="brief:{id}" convention for old rows.
            if sub.brief_id is not None:
                ent.unlocked_brief_ids.add(int(sub.brief_id))
            else:
                ref = sub.provider_ref or ""
                if ref.startswith("brief:"):
                    try:
                        ent.unlocked_brief_ids.add(int(ref.split(":", 1)[1]))
                    except ValueError:
                        pass
    return ent
