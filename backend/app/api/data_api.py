"""Data API: API key management + rate-limited data export for monetization."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user_required
from app.core.entitlement import compute_entitlement
from app.core.logging import logger
from app.db.session import get_session
from app.models.api_key import ApiKey
from app.models.pain_point import PainPoint
from app.models.user import User

router = APIRouter(prefix="/api/data", tags=["data-api"])

KEY_PREFIX_LEN = 8
RAW_KEY_BYTES = 32


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKeyOut(BaseModel):
    id: int
    name: str | None
    key_prefix: str
    active: bool
    last_used_at: str | None
    request_count: int


class ApiKeyCreateOut(BaseModel):
    id: int
    name: str | None
    api_key: str  # only returned once!
    message: str


# ---------- API key management ----------


@router.get("/keys", response_model=list[ApiKeyOut])
def list_keys(
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> list[ApiKeyOut]:
    rows = list(
        db.execute(
            select(ApiKey).where(ApiKey.user_id == user.id)
        ).scalars()
    )
    return [
        ApiKeyOut(
            id=r.id,
            name=r.name,
            key_prefix=r.key_prefix,
            active=r.active,
            last_used_at=r.last_used_at.isoformat() if r.last_used_at else None,
            request_count=r.request_count,
        )
        for r in rows
    ]


@router.post("/keys", response_model=ApiKeyCreateOut)
def create_key(
    name: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> ApiKeyCreateOut:
    # Check entitlement: only pro users can create API keys
    ent = compute_entitlement(db, user.id)
    if ent.plan == "free":
        raise HTTPException(status_code=402, detail="API access requires a Pro subscription")

    raw = "dr_" + secrets.token_hex(RAW_KEY_BYTES)
    key_hash = _hash_key(raw)
    key_prefix = raw[:KEY_PREFIX_LEN]

    entry = ApiKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info("api_key created user={} id={}", user.id, entry.id)
    return ApiKeyCreateOut(
        id=entry.id,
        name=entry.name,
        api_key=raw,
        message="Store this key securely — it will not be shown again.",
    )


@router.delete("/keys/{key_id}")
def revoke_key(
    key_id: int,
    db: Session = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, bool]:
    key = db.get(ApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(status_code=404, detail="not found")
    key.active = False
    db.commit()
    return {"ok": True}


# ---------- Data export (rate-limited) ----------

RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX = 100  # requests per window


def _authenticate_api_key(request: Request, db: Session) -> ApiKey:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="bearer token required")
    raw_key = auth[7:].strip()
    key_hash = _hash_key(raw_key)
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
    if key is None or not key.active:
        raise HTTPException(status_code=401, detail="invalid or revoked API key")

    # Rate limit check
    now = datetime.now(tz=timezone.utc)
    if key.last_used_at is not None:
        elapsed = (now - key.last_used_at).total_seconds()
        if elapsed < RATE_LIMIT_WINDOW and key.request_count >= RATE_LIMIT_MAX:
            raise HTTPException(status_code=429, detail="rate limit exceeded (100 req/hr)")
        if elapsed >= RATE_LIMIT_WINDOW:
            key.request_count = 0

    key.request_count += 1
    key.last_used_at = now
    db.commit()
    return key


class PainPointExport(BaseModel):
    id: int
    pain: str
    target_user: str | None
    total_score: float | None
    go_no_go: str | None
    frequency_signal: str
    industry: str | None


@router.get("/painpoints", response_model=list[PainPointExport])
def export_painpoints(
    request: Request,
    db: Session = Depends(get_session),
    limit: int = Query(100, ge=1, le=500),
    min_score: float = Query(0, ge=0, le=100),
    industry: str | None = None,
) -> list[PainPointExport]:
    _authenticate_api_key(request, db)

    q = select(PainPoint).where(
        PainPoint.total_score.is_not(None),
        PainPoint.total_score >= min_score,
    )
    if industry:
        q = q.where(PainPoint.industry == industry)
    q = q.order_by(PainPoint.total_score.desc()).limit(limit)

    rows = list(db.execute(q).scalars())
    return [
        PainPointExport(
            id=pp.id,
            pain=pp.pain,
            target_user=pp.target_user,
            total_score=float(pp.total_score) if pp.total_score else None,
            go_no_go=pp.go_no_go,
            frequency_signal=pp.frequency_signal,
            industry=pp.industry,
        )
        for pp in rows
    ]
