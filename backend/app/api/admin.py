"""Admin-only dashboard API.

Gated by the existing `User.is_admin` flag (set manually via SQL/CLI for
trusted operators). Provides a small set of read-only endpoints used by
the SSR `/admin` page on the frontend.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.deps import current_user_required
from app.core import llm_router
from app.db.session import get_session
from app.models.email_dispatch import EmailDispatch
from app.models.llm_usage_log import LLMUsageLog
from app.models.payment_event import PaymentEvent
from app.models.referral_grant import ReferralGrant
from app.models.social_post import SocialPost
from app.models.subscription import Subscription
from app.models.user import User
from app.models.waitlist import WaitlistEntry

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: User = Depends(current_user_required)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin only")
    return user


# ---------- response schemas ----------

class StatsCard(BaseModel):
    label: str
    value: int | float
    note: str | None = None


class PlanCount(BaseModel):
    plan: str
    active: int
    canceled: int
    refunded: int


class RecentEvent(BaseModel):
    id: int
    event_id: str
    type: str
    received_at: datetime
    user_id: int | None
    subscription_id: int | None


class TopReferrer(BaseModel):
    user_id: int
    email: str
    referral_code: str | None
    grants: int
    total_bonus_days: int


class StatsOut(BaseModel):
    cards: list[StatsCard]
    plans: list[PlanCount]
    recent_events: list[RecentEvent]
    top_referrers: list[TopReferrer]


# ---------- endpoint ----------

@router.get("/stats", response_model=StatsOut)
def stats(
    db: Session = Depends(get_session),
    _: User = Depends(_require_admin),
) -> StatsOut:
    now = datetime.now(tz=timezone.utc)
    last_30 = now - timedelta(days=30)

    total_users = int(db.scalar(select(func.count()).select_from(User)) or 0)
    new_users_30d = int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= last_30)
        )
        or 0
    )
    waitlist_total = int(
        db.scalar(select(func.count()).select_from(WaitlistEntry)) or 0
    )
    active_subs = int(
        db.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.status == "active")
        )
        or 0
    )
    # Crude MRR: sum amount_cents of active recurring subs.
    # Currency depends on provider: Stripe = USD cents, redeem = CNY cents.
    mrr_cents = int(
        db.scalar(
            select(func.coalesce(func.sum(Subscription.amount_cents), 0))
            .where(Subscription.status == "active")
            .where(Subscription.plan.in_(("weekly_pro", "studio")))
        )
        or 0
    )
    mrr_currency = "USD"
    grant_total = int(
        db.scalar(select(func.count()).select_from(ReferralGrant)) or 0
    )

    cards = [
        StatsCard(label="Users", value=total_users, note=f"+{new_users_30d} in 30d"),
        StatsCard(label="Waitlist", value=waitlist_total),
        StatsCard(label="Active subs", value=active_subs),
        StatsCard(label=f"MRR ({mrr_currency})", value=round(mrr_cents / 100, 2)),
        StatsCard(label="Referral grants", value=grant_total),
    ]

    # Plan distribution
    rows = db.execute(
        select(Subscription.plan, Subscription.status, func.count())
        .group_by(Subscription.plan, Subscription.status)
    ).all()
    by_plan: dict[str, dict[str, int]] = {}
    for plan, status, n in rows:
        by_plan.setdefault(plan, {"active": 0, "canceled": 0, "refunded": 0})
        if status in by_plan[plan]:
            by_plan[plan][status] = int(n)
    plans = [
        PlanCount(
            plan=p,
            active=v["active"],
            canceled=v["canceled"],
            refunded=v["refunded"],
        )
        for p, v in sorted(by_plan.items())
    ]

    # Recent payment events
    recent_rows: list[PaymentEvent] = list(
        db.execute(
            select(PaymentEvent)
            .order_by(desc(PaymentEvent.received_at))
            .limit(20)
        ).scalars()
    )
    recent_events = [
        RecentEvent(
            id=r.id,
            event_id=r.event_id,
            type=r.type,
            received_at=r.received_at,
            user_id=r.user_id,
            subscription_id=r.subscription_id,
        )
        for r in recent_rows
    ]

    # Top referrers (by grants)
    ref_rows: list[Any] = list(
        db.execute(
            select(
                User.id,
                User.email,
                User.referral_code,
                func.count(ReferralGrant.id),
                func.coalesce(func.sum(ReferralGrant.bonus_days), 0),
            )
            .join(ReferralGrant, ReferralGrant.referrer_user_id == User.id)
            .group_by(User.id)
            .order_by(desc(func.count(ReferralGrant.id)))
            .limit(10)
        ).all()
    )
    top_referrers = [
        TopReferrer(
            user_id=int(r[0]),
            email=str(r[1]),
            referral_code=r[2],
            grants=int(r[3]),
            total_bonus_days=int(r[4]),
        )
        for r in ref_rows
    ]

    return StatsOut(
        cards=cards,
        plans=plans,
        recent_events=recent_events,
        top_referrers=top_referrers,
    )


# ---------- D15: dispatches + social queue ----------

class DispatchRow(BaseModel):
    id: int
    campaign: str
    email: str
    status: str
    attempts: int
    sent_at: datetime | None
    error: str | None


class SocialPostRow(BaseModel):
    id: int
    platform: str
    status: str
    kind: str
    title: str | None
    body: str
    url: str | None
    external_id: str | None
    error: str | None
    posted_at: datetime | None
    created_at: datetime


@router.get("/dispatches")
def dispatches(
    campaign: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_session),
    _: User = Depends(_require_admin),
) -> dict[str, Any]:
    q = select(EmailDispatch).order_by(desc(EmailDispatch.id)).limit(min(limit, 200))
    if campaign:
        q = q.where(EmailDispatch.campaign == campaign)
    rows = list(db.execute(q).scalars())

    by_status: dict[str, int] = {}
    if campaign:
        for status, n in db.execute(
            select(EmailDispatch.status, func.count())
            .where(EmailDispatch.campaign == campaign)
            .group_by(EmailDispatch.status)
        ).all():
            by_status[str(status)] = int(n)

    return {
        "campaign": campaign,
        "rows": [
            DispatchRow(
                id=r.id,
                campaign=r.campaign,
                email=r.email,
                status=r.status,
                attempts=r.attempts,
                sent_at=r.sent_at,
                error=r.error,
            ).model_dump()
            for r in rows
        ],
        "summary": by_status,
    }


@router.get("/social-posts")
def social_posts(
    platform: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_session),
    _: User = Depends(_require_admin),
) -> list[SocialPostRow]:
    q = select(SocialPost).order_by(desc(SocialPost.id)).limit(min(limit, 200))
    if platform:
        q = q.where(SocialPost.platform == platform)
    if status:
        q = q.where(SocialPost.status == status)
    return [
        SocialPostRow(
            id=r.id,
            platform=r.platform,
            status=r.status,
            kind=r.kind,
            title=r.title,
            body=r.body,
            url=r.url,
            external_id=r.external_id,
            error=r.error,
            posted_at=r.posted_at,
            created_at=r.created_at,
        )
        for r in db.execute(q).scalars()
    ]


# ---------- D17: LLM budget + provider mix ----------

class LLMProviderRow(BaseModel):
    provider: str
    model: str
    calls: int
    success: int
    failures: int
    tokens: int
    cost_cny: float


class LLMBudgetOut(BaseModel):
    spent_cny: float
    limit_cny: float
    remaining_cny: float
    used_pct: float
    over: bool
    by_provider: list[LLMProviderRow]
    top_purposes: list[dict[str, Any]]


@router.get("/llm-budget", response_model=LLMBudgetOut)
def llm_budget(
    db: Session = Depends(get_session),
    _: User = Depends(_require_admin),
) -> LLMBudgetOut:
    s = llm_router.budget_status()
    rows = llm_router.by_provider_today()
    today = datetime.combine(
        datetime.now(tz=timezone.utc).date(), datetime.min.time(), tzinfo=timezone.utc
    )
    purpose_rows = list(
        db.execute(
            select(
                LLMUsageLog.purpose,
                func.count(),
                func.coalesce(func.sum(LLMUsageLog.cost_cny), 0.0),
            )
            .where(LLMUsageLog.created_at >= today)
            .group_by(LLMUsageLog.purpose)
            .order_by(desc(func.coalesce(func.sum(LLMUsageLog.cost_cny), 0.0)))
            .limit(10)
        ).all()
    )
    return LLMBudgetOut(
        spent_cny=round(s.spent_cny, 4),
        limit_cny=s.limit_cny,
        remaining_cny=round(s.remaining_cny, 4),
        used_pct=round(s.used_pct, 1),
        over=s.over,
        by_provider=[
            LLMProviderRow(
                provider=r.provider, model=r.model, calls=r.calls,
                success=r.success, failures=r.failures,
                tokens=r.tokens, cost_cny=round(r.cost_cny, 4),
            )
            for r in rows
        ],
        top_purposes=[
            {"purpose": str(p), "calls": int(n), "cost_cny": round(float(c), 4)}
            for p, n, c in purpose_rows
        ],
    )


__all__ = ["router"]
