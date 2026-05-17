"""Magic-link authentication.

Flow:
1. POST /api/auth/request-link  { email }
   -> creates the user lazily, mails them a one-time link.
   -> in dev (or when SMTP not configured) the link is also returned in JSON,
      so the contributor doesn't need a real inbox.
2. GET  /api/auth/verify?token=...
   -> verifies, sets HttpOnly cookie `dr_session`, redirects to ?next=
3. GET  /api/auth/me
   -> returns current user + entitlement (or 401 if anonymous).
4. POST /api/auth/logout
   -> clears the cookie.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    SESSION_COOKIE,
    current_entitlement,
    current_user_required,
)
from app.core.email_templates import login_welcome
from app.core.entitlement import Entitlement
from app.core.locale import pick_locale, stored_or
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.core.referral import apply_referral, ensure_referral_code
from app.core.security import (
    TokenError,
    decode_jwt,
    issue_magic_link_token,
    issue_session_token,
)
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_TTL_DAYS = 30


class RequestLinkIn(BaseModel):
    email: EmailStr
    next: str | None = None
    ref: str | None = None  # D13: referral code from ?ref=XXXX cookie
    # D18: explicit locale hint from the frontend cookie. Falls back to
    # the request `Accept-Language` header when missing.
    locale: str | None = None


class RequestLinkOut(BaseModel):
    sent: bool
    smtp_enabled: bool
    # In dev only: the verification URL is included so the contributor can
    # click it without a real inbox. NEVER returned in prod.
    debug_link: str | None = None


class MeOut(BaseModel):
    id: int
    email: str
    name: str | None
    is_admin: bool
    entitlement: dict
    referral_code: str | None = None
    referral_url: str | None = None


def _build_verify_url(base_url: str, token: str, next_path: str | None) -> str:
    params = {"token": token}
    if next_path:
        params["next"] = next_path
    return f"{base_url.rstrip('/')}/api/auth/verify?{urlencode(params)}"


def _get_or_create_user(
    db: Session, email: str, *, locale: str | None = None
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, is_active=True, is_admin=False, locale=locale)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif locale and not user.locale:
        # Backfill: existing user without a stored locale picks up the hint.
        user.locale = locale
        db.commit()
    return user


@router.post("/request-link", response_model=RequestLinkOut)
def request_link(
    body: RequestLinkIn,
    request: Request,
    db: Session = Depends(get_session),
) -> RequestLinkOut:
    email = body.email.strip().lower()
    locale = pick_locale(
        explicit=body.locale,
        header=request.headers.get("accept-language"),
    )
    user = _get_or_create_user(db, email, locale=locale)
    token = issue_magic_link_token(email, ref=body.ref)
    # Prefer the configured public URL (frontend) so magic links go through
    # Next.js rewrites and the cookie lands on the user-facing domain.
    base = (settings.public_base_url or str(request.base_url)).rstrip("/")
    verify_url = _build_verify_url(base, token, body.next)

    text = (
        f"Hi {user.name or email},\n\n"
        f"Click the link below to sign in to DemandRadar (valid 15 min):\n\n"
        f"{verify_url}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    html = (
        f"<p>Hi {user.name or email},</p>"
        f"<p>Click below to sign in to DemandRadar (valid 15 min):</p>"
        f'<p><a href="{verify_url}">Sign in</a></p>'
        f"<p style='color:#888;font-size:12px'>{verify_url}</p>"
    )
    sent = False
    if smtp_enabled():
        sent = send_email(
            to=email, subject="[DemandRadar] Sign-in link", text=text, html=html
        )

    debug_link = verify_url if (settings.is_dev or not smtp_enabled()) else None
    if debug_link:
        logger.info("magic-link issued for {} -> {}", email, debug_link)
    return RequestLinkOut(
        sent=sent, smtp_enabled=smtp_enabled(), debug_link=debug_link
    )


@router.get("/verify")
def verify(
    token: str,
    next: str | None = None,
    db: Session = Depends(get_session),
) -> Response:
    try:
        payload = decode_jwt(token)
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid or expired link ({e})",
        )
    if payload.get("kind") != "magic":
        raise HTTPException(status_code=400, detail="not a magic link token")
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="missing email")

    user = _get_or_create_user(db, email)
    is_first_login = user.last_login_at is None
    user.last_login_at = datetime.now(tz=timezone.utc)

    # D13: apply incoming referral code (one-shot — no-op if already linked).
    apply_referral(db, user, payload.get("ref"))
    # And issue this user their own code so /account can show it immediately.
    referral_code = ensure_referral_code(db, user)
    db.commit()

    # Best-effort welcome email on the very first verification.
    if is_first_login and smtp_enabled():
        try:
            base = settings.public_base_url.rstrip("/")
            ref_url = f"{base}/?ref={referral_code}"
            subject, txt, html = login_welcome(
                user.email,
                referral_url=ref_url,
                locale=stored_or("en", user.locale),
            )
            send_email(to=user.email, subject=subject, text=txt, html=html)
        except Exception as exc:  # noqa: BLE001
            logger.warning("login welcome email failed: {}", exc)

    session_token = issue_session_token(user.id, user.email, ttl_days=SESSION_TTL_DAYS)
    redirect_to = next or "/account"
    resp = RedirectResponse(url=redirect_to, status_code=302)
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=SESSION_TTL_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=not settings.is_dev,
        path="/",
    )
    return resp


@router.get("/me", response_model=MeOut)
def me(
    user: User = Depends(current_user_required),
    ent: Entitlement = Depends(current_entitlement),
    db: Session = Depends(get_session),
) -> MeOut:
    code = ensure_referral_code(db, user)
    db.commit()
    base = settings.public_base_url.rstrip("/")
    return MeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        is_admin=user.is_admin,
        entitlement=ent.to_dict(),
        referral_code=code,
        referral_url=f"{base}/?ref={code}",
    )


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


# Optional: programmatic exchange (useful for SPAs that prefer Bearer over cookies).
class ExchangeIn(BaseModel):
    token: str


class ExchangeOut(BaseModel):
    access_token: str
    expires_in: int


@router.post("/exchange", response_model=ExchangeOut)
def exchange(
    body: ExchangeIn, db: Session = Depends(get_session)
) -> ExchangeOut:
    """Trade a magic-link token for a Bearer session JWT (no cookie)."""
    try:
        payload = decode_jwt(body.token)
    except TokenError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if payload.get("kind") != "magic":
        raise HTTPException(status_code=400, detail="not a magic link token")
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="missing email")

    user = _get_or_create_user(db, email)
    user.last_login_at = datetime.now(tz=timezone.utc)
    apply_referral(db, user, payload.get("ref"))
    ensure_referral_code(db, user)
    db.commit()

    tok = issue_session_token(user.id, user.email, ttl_days=SESSION_TTL_DAYS)
    return ExchangeOut(access_token=tok, expires_in=SESSION_TTL_DAYS * 86400)
