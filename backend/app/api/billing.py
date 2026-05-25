"""Billing endpoints.

MVP design:
- /api/billing/redeem      consume a CLI-issued signed redeem code
                            -> creates an active Subscription row
- /api/billing/subscription return current user's active subscriptions + entitlement
- /api/billing/checkout    placeholder that, when STRIPE_SECRET_KEY is set,
                            would create a real Stripe Checkout session.
                            Without it we fall back to "redeem code" mode.
- /api/billing/webhook/stripe stub that Stripe would call - logs and 200s.

This is deliberately small: the redeem path lets us monetise ¥99 项目书 and
¥29.9 周报 today via WeChat/Alipay manually (admin issues the code in the
order confirmation), with zero PCI/payment-channel integration in MVP.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing import handle_event
from app.core import payments
from app.core.config import settings
from app.core.deps import current_entitlement, current_user_required
from app.core.entitlement import Entitlement, compute_entitlement
from app.core.logging import logger
from app.core.payments import PLANS, PaymentsDisabled
from app.core.security import (
    TokenError,
    parse_redeem_code,
    subscription_expiry,
)
from app.db.session import get_session
from app.models.brief import Brief
from app.models.redeem_code import RedeemCode
from app.models.share_unlock import ShareUnlock
from app.models.subscription import Subscription
from app.models.user import User

router = APIRouter(prefix="/api/billing", tags=["billing"])


class RedeemIn(BaseModel):
    code: str = Field(min_length=10)


class RedeemOut(BaseModel):
    ok: bool
    plan: str
    expires_at: datetime | None
    brief_id: int | None
    entitlement: dict


class SubscriptionRow(BaseModel):
    id: int
    plan: str
    status: str
    provider: str
    provider_ref: str | None
    started_at: datetime | None
    expires_at: datetime | None


class SubscriptionOut(BaseModel):
    user_id: int
    items: list[SubscriptionRow]
    entitlement: dict


class CheckoutIn(BaseModel):
    plan: str
    brief_id: int | None = None
    success_url: str | None = None  # optional override; defaults to /account?paid=1
    cancel_url: str | None = None


class CheckoutOut(BaseModel):
    mode: str  # "stripe" | "redeem_only"
    url: str | None
    session_id: str | None = None
    message: str


class PortalOut(BaseModel):
    url: str


class RefundOut(BaseModel):
    ok: bool
    subscription_id: int
    refunded: bool
    canceled: bool
    details: dict


@router.post("/redeem", response_model=RedeemOut)
def redeem(
    body: RedeemIn,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> RedeemOut:
    try:
        payload = parse_redeem_code(body.code)
    except TokenError as e:
        raise HTTPException(status_code=400, detail=f"bad code: {e}")

    nonce = payload.get("nonce")
    if not nonce:
        raise HTTPException(status_code=400, detail="missing nonce")

    # one-shot guard
    used = db.scalar(select(RedeemCode).where(RedeemCode.nonce == nonce))
    if used is not None:
        raise HTTPException(status_code=409, detail="code already redeemed")

    plan = payload["plan"]
    days = int(payload.get("days") or 30)
    brief_id = payload.get("brief_id")

    if plan == "brief_oneoff":
        if brief_id is None:
            raise HTTPException(status_code=400, detail="brief_oneoff code missing brief_id")
        if db.get(Brief, int(brief_id)) is None:
            raise HTTPException(status_code=404, detail="brief not found")

    started = datetime.now(tz=timezone.utc)
    expires = subscription_expiry(days) if plan != "brief_oneoff" else None

    sub = Subscription(
        user_id=user.id,
        plan=plan,
        status="active",
        provider="redeem",
        provider_ref=f"brief:{brief_id}" if brief_id is not None else f"redeem:{nonce}",
        brief_id=int(brief_id) if brief_id is not None else None,
        amount_cny=None,
        started_at=started,
        expires_at=expires,
    )
    db.add(sub)
    db.add(
        RedeemCode(
            nonce=str(nonce),
            user_id=user.id,
            plan=plan,
            days=days,
            brief_id=int(brief_id) if brief_id is not None else None,
            redeemed_at=started,
        )
    )
    db.commit()
    db.refresh(sub)

    ent = compute_entitlement(db, user)
    logger.info("redeem ok user_id={} plan={} brief_id={}", user.id, plan, brief_id)
    return RedeemOut(
        ok=True,
        plan=plan,
        expires_at=expires,
        brief_id=int(brief_id) if brief_id is not None else None,
        entitlement=ent.to_dict(),
    )


@router.get("/subscription", response_model=SubscriptionOut)
def my_subscription(
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
    ent: Entitlement = Depends(current_entitlement),
) -> SubscriptionOut:
    rows = list(
        db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        ).scalars()
    )
    return SubscriptionOut(
        user_id=user.id,
        items=[
            SubscriptionRow(
                id=r.id,
                plan=r.plan,
                status=r.status,
                provider=r.provider,
                provider_ref=r.provider_ref,
                started_at=r.started_at,
                expires_at=r.expires_at,
            )
            for r in rows
        ],
        entitlement=ent.to_dict(),
    )


@router.post("/checkout", response_model=CheckoutOut)
def checkout(
    body: CheckoutIn,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> CheckoutOut:
    """Create a Stripe Checkout Session for the requested plan.

    Falls back to a friendly message when Stripe isn't configured (so we can
    still operate in redeem-code-only mode).
    """
    if body.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"unknown plan: {body.plan}")
    if PLANS[body.plan].needs_brief_id:
        if body.brief_id is None:
            raise HTTPException(
                status_code=400, detail="brief_id is required for brief_oneoff"
            )
        if db.get(Brief, body.brief_id) is None:
            raise HTTPException(status_code=404, detail="brief not found")

    if not payments.is_enabled():
        return CheckoutOut(
            mode="redeem_only",
            url=None,
            message=(
                "Stripe is not configured on this server. Pay manually via "
                "WeChat/Alipay and we'll email you a redeem code."
            ),
        )

    base = settings.public_base_url.rstrip("/")
    success = body.success_url or f"{base}/account?paid=1&session={{CHECKOUT_SESSION_ID}}"
    cancel = body.cancel_url or f"{base}/pricing?canceled=1"

    try:
        session = payments.create_checkout_session(
            user,
            plan=body.plan,
            brief_id=body.brief_id,
            success_url=success,
            cancel_url=cancel,
        )
    except (PaymentsDisabled, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ensure_customer may have set user.stripe_customer_id; persist it.
    db.commit()

    logger.info(
        "checkout session created user_id={} plan={} session_id={}",
        user.id,
        body.plan,
        session.get("id"),
    )
    return CheckoutOut(
        mode="stripe",
        url=session.get("url"),
        session_id=session.get("id"),
        message="redirect the user to `url` to complete payment",
    )


@router.post("/portal", response_model=PortalOut)
def portal(
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> PortalOut:
    """Open a Stripe Customer Portal session."""
    if not payments.is_enabled():
        raise HTTPException(status_code=400, detail="stripe disabled")
    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=400, detail="no stripe customer; complete a checkout first"
        )
    try:
        sess = payments.create_billing_portal_session(
            user, return_url=settings.public_base_url.rstrip("/") + "/account"
        )
    except (PaymentsDisabled, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PortalOut(url=sess["url"])


@router.post("/refund/{subscription_id}", response_model=RefundOut)
def admin_refund(
    subscription_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> RefundOut:
    """Admin-only refund. Cancels the recurring sub and refunds one-time charges."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin only")
    sub = db.get(Subscription, subscription_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    if sub.provider != "stripe":
        raise HTTPException(
            status_code=400, detail="only stripe subscriptions are refundable here"
        )
    try:
        result = payments.refund_subscription(sub)
    except (PaymentsDisabled, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    sub.status = "refunded" if result["refunded"] else ("canceled" if result["canceled"] else sub.status)
    db.commit()
    return RefundOut(
        ok=True,
        subscription_id=sub.id,
        refunded=bool(result["refunded"]),
        canceled=bool(result["canceled"]),
        details=result.get("details", {}),
    )


@router.post("/webhook/stripe", status_code=status.HTTP_200_OK)
def stripe_webhook(
    request: Request,
    db: Session = Depends(get_session),
) -> dict[str, object]:
    """Verify the signature and dispatch to handlers. Always returns 200 so
    Stripe stops retrying — errors are recorded as a `<type>__failed` row."""
    body = request.body()
    sig = request.headers.get("stripe-signature", "")
    if not sig:
        raise HTTPException(status_code=400, detail="missing stripe-signature")
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="webhook secret not configured")
    try:
        event = payments.verify_webhook(body, sig)
    except (PaymentsDisabled, ValueError) as e:
        logger.warning("webhook verify failed: {}", e)
        raise HTTPException(status_code=400, detail=str(e))
    return handle_event(db, event)


# ---------- D20: share-to-unlock (viral growth) ----------

import secrets as _secrets

SHARE_TOKEN_BYTES = 16  # 32-char hex token


class ShareUnlockIn(BaseModel):
    brief_id: int | None = None
    pain_point_id: int | None = None
    platform: str | None = None


class ShareUnlockOut(BaseModel):
    share_token: str
    share_url: str
    twitter_url: str | None = None
    message: str


class ClaimShareIn(BaseModel):
    share_token: str = Field(min_length=8)


class ClaimShareOut(BaseModel):
    ok: bool
    brief_id: int | None = None
    message: str


def _build_share_text(brief_id: int | None, pain_point_id: int | None) -> str:
    if brief_id:
        return "发现一个高价值痛点，DemandRadar 已经生成了完整项目书 →"
    if pain_point_id:
        return "这个需求痛点很有意思，来看看 DemandRadar 的分析 →"
    return "用 DemandRadar 发现下一个创业机会 →"


@router.post("/share-unlock", response_model=ShareUnlockOut)
def create_share_unlock(
    body: ShareUnlockIn,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> ShareUnlockOut:
    token = _secrets.token_hex(SHARE_TOKEN_BYTES)
    base = settings.public_base_url.rstrip("/")

    share_url = f"{base}/?share={token}"
    if body.brief_id:
        share_url += f"&bid={body.brief_id}"
    elif body.pain_point_id:
        share_url += f"&pid={body.pain_point_id}"

    text = _build_share_text(body.brief_id, body.pain_point_id)
    twitter_url = (
        f"https://twitter.com/intent/tweet?text={text}&url={share_url}"
    )

    entry = ShareUnlock(
        sharer_user_id=user.id,
        share_token=token,
        brief_id=body.brief_id,
        pain_point_id=body.pain_point_id,
        platform=body.platform,
    )
    db.add(entry)
    db.commit()

    logger.info("share_unlock created user={} token={} brief={}", user.id, token, body.brief_id)
    return ShareUnlockOut(
        share_token=token,
        share_url=share_url,
        twitter_url=twitter_url,
        message="分享此链接，当有人通过链接注册后，你和对方都将获得 1 个免费 Brief 解锁！",
    )


@router.post("/share-unlock/claim", response_model=ClaimShareOut)
def claim_share_unlock(
    body: ClaimShareIn,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> ClaimShareOut:
    entry = db.scalar(
        select(ShareUnlock).where(ShareUnlock.share_token == body.share_token)
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="share token not found")

    if entry.claimed_by_user_id is not None and entry.claimed_by_user_id != user.id:
        raise HTTPException(status_code=409, detail="share already claimed by another user")

    now = datetime.now(tz=timezone.utc)
    brief_id = entry.brief_id

    if not entry.claimer_rewarded:
        if brief_id is not None:
            sub = Subscription(
                user_id=user.id,
                plan="brief_oneoff",
                status="active",
                provider="share_unlock",
                provider_ref=f"share:{entry.share_token}",
                brief_id=brief_id,
                started_at=now,
                expires_at=None,
            )
            db.add(sub)
        entry.claimer_rewarded = True
        entry.claimed_by_user_id = user.id
        entry.claimed_at = now

    if not entry.sharer_rewarded:
        if brief_id is not None:
            sharer_sub = Subscription(
                user_id=entry.sharer_user_id,
                plan="brief_oneoff",
                status="active",
                provider="share_unlock",
                provider_ref=f"share_reward:{entry.share_token}",
                brief_id=brief_id,
                started_at=now,
                expires_at=None,
            )
            db.add(sharer_sub)
        entry.sharer_rewarded = True

    db.commit()
    logger.info(
        "share_unlock claimed token={} claimer={} sharer={} brief={}",
        entry.share_token, user.id, entry.sharer_user_id, brief_id,
    )
    return ClaimShareOut(
        ok=True,
        brief_id=brief_id,
        message=f"解锁成功！你现在可以查看 Brief #{brief_id} 的完整内容。",
    )


# ---------- E2E helpers (mounted only when E2E_ENABLE=1) ----------
# These endpoints exist purely so the Playwright suite can drive the system
# without needing a real Stripe account or a writable inbox. Authorisation is
# the existing admin backdoor: X-Admin-Secret must equal APP_SECRET_KEY.

import os as _os  # noqa: E402

if _os.environ.get("E2E_ENABLE") == "1":
    from app.core.security import issue_redeem_code as _issue_redeem_code

    def _require_admin_secret(request: Request) -> None:
        secret = request.headers.get("x-admin-secret", "")
        if not settings.app_secret_key or secret != settings.app_secret_key:
            raise HTTPException(status_code=403, detail="bad admin secret")

    class _E2EIssueIn(BaseModel):
        plan: str
        days: int = 30
        brief_id: int | None = None

    @router.post("/_e2e/issue-code")
    def _e2e_issue_code(
        body: _E2EIssueIn, request: Request
    ) -> dict[str, str]:
        _require_admin_secret(request)
        code = _issue_redeem_code(
            body.plan, days=body.days, brief_id=body.brief_id, note="e2e"
        )
        return {"code": code}

    class _E2EPromoteIn(BaseModel):
        email: str

    @router.post("/_e2e/promote")
    def _e2e_promote(
        body: _E2EPromoteIn,
        request: Request,
        db: Session = Depends(get_session),
    ) -> dict[str, bool]:
        _require_admin_secret(request)
        u = db.scalar(select(User).where(User.email == body.email.lower()))
        if u is None:
            raise HTTPException(status_code=404, detail="user not found")
        u.is_admin = True
        db.commit()
        return {"ok": True}

    class _E2ESeedBriefIn(BaseModel):
        title: str = "E2E Test Brief"
        markdown: str = "# E2E\n\nUnlocked content for e2e tests."
        pain: str = "e2e-pain"

    @router.post("/_e2e/seed-brief")
    def _e2e_seed_brief(
        body: _E2ESeedBriefIn,
        request: Request,
        db: Session = Depends(get_session),
    ) -> dict[str, int]:
        from app.models.pain_point import PainPoint
        _require_admin_secret(request)
        pp = PainPoint(pain=body.pain, target_user="e2e", total_score=85.0, go_no_go="go")
        db.add(pp)
        db.flush()
        b = Brief(
            pain_point_id=pp.id,
            title=body.title,
            markdown=body.markdown,
            visibility="paid",
            version=1,
        )
        db.add(b)
        db.commit()
        return {"brief_id": b.id, "pain_point_id": pp.id}
