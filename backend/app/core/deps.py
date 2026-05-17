"""FastAPI dependency injectors for auth + entitlement.

Reads the session token from either:
- HttpOnly cookie `dr_session` (browser flow), or
- `Authorization: Bearer <jwt>` header (programmatic / mobile)

Anonymous callers get `current_user_optional() == None` and an empty
Entitlement (everyone-can-read-public). For locked endpoints we still
honour `X-Unlock-Token == APP_SECRET_KEY` as an admin master override
so prior tests/CLI keep working.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.entitlement import ANON, Entitlement, compute_entitlement
from app.core.security import TokenError, decode_jwt
from app.db.session import get_session
from app.models.user import User

SESSION_COOKIE = "dr_session"


def _extract_token(
    cookie_value: Optional[str],
    auth_header: Optional[str],
) -> Optional[str]:
    if cookie_value:
        return cookie_value
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip() or None
    return None


def current_user_optional(
    db: Session = Depends(get_session),
    dr_session: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Optional[User]:
    """Returns the User row or None. Never raises on missing/invalid token."""
    token = _extract_token(dr_session, authorization)
    if not token:
        return None
    try:
        payload = decode_jwt(token)
    except TokenError:
        return None
    if payload.get("kind") != "session":
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        uid = int(sub)
    except (TypeError, ValueError):
        return None
    user = db.get(User, uid)
    if user is None or not user.is_active:
        return None
    return user


def current_user_required(
    user: Optional[User] = Depends(current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="login required"
        )
    return user


def current_entitlement(
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(current_user_optional),
    x_unlock_token_header: Optional[str] = Header(
        default=None, alias="X-Unlock-Token"
    ),
    x_unlock_token: Optional[str] = Query(default=None),
) -> Entitlement:
    """Effective entitlement = user subscriptions ∪ admin master token override.

    The admin master token may arrive via either the `X-Unlock-Token` header
    or the `?x_unlock_token=` query string (the latter is what legacy
    D7/D8 tests use).
    """
    if user is None:
        ent = Entitlement()
    else:
        ent = compute_entitlement(db, user)

    master = x_unlock_token_header or x_unlock_token
    if master and master == settings.app_secret_key:
        ent.is_admin = True
    return ent


__all__ = [
    "SESSION_COOKIE",
    "ANON",
    "current_user_optional",
    "current_user_required",
    "current_entitlement",
]
