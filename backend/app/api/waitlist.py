"""Waitlist endpoint - capture early subscribers' emails before MVP launch.

Storage: Postgres `waitlist_entries` (since D2). Day-1 JSONL is backfilled
automatically on first request via :func:`_backfill_jsonl_once`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.core.email_templates import waitlist_welcome
from app.core.locale import pick_locale
from app.core.logging import logger
from app.core.notify import send_email, smtp_enabled
from app.db.session import get_session
from app.models.waitlist import WaitlistEntry

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

_LEGACY_JSONL = BASE_DIR / "data" / "waitlist.jsonl"
_BACKFILL_DONE = False


class WaitlistIn(BaseModel):
    email: EmailStr
    source: str = Field("landing", max_length=64)
    note: str | None = Field(None, max_length=500)
    # D18: explicit locale hint from the frontend cookie. Falls back to
    # parsing the `Accept-Language` request header.
    locale: str | None = Field(None, max_length=8)


class WaitlistOut(BaseModel):
    ok: bool
    count: int


def _backfill_jsonl_once(db: Session) -> None:
    """One-shot import of legacy JSONL records into Postgres."""
    global _BACKFILL_DONE
    if _BACKFILL_DONE or not _LEGACY_JSONL.exists():
        _BACKFILL_DONE = True
        return
    import json

    imported = 0
    with _LEGACY_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            email = (rec.get("email") or "").strip()
            if not email:
                continue
            entry = WaitlistEntry(
                email=email,
                source=rec.get("source") or "landing",
                note=rec.get("note"),
            )
            db.add(entry)
            try:
                db.commit()
                imported += 1
            except IntegrityError:
                db.rollback()  # duplicate, skip
    if imported:
        logger.info("waitlist backfill imported {} legacy entries", imported)
        # Rename the file so we never re-import.
        try:
            _LEGACY_JSONL.rename(_LEGACY_JSONL.with_suffix(".jsonl.imported"))
        except OSError:
            pass
    _BACKFILL_DONE = True


@router.post("", response_model=WaitlistOut)
async def join_waitlist(
    payload: WaitlistIn,
    request: Request,
    db: Session = Depends(get_session),
) -> WaitlistOut:
    _backfill_jsonl_once(db)

    locale = pick_locale(
        explicit=payload.locale,
        header=request.headers.get("accept-language"),
    )
    entry = WaitlistEntry(
        email=payload.email,
        source=payload.source,
        note=payload.note,
        ip=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        locale=locale,
    )
    db.add(entry)
    new_signup = True
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        new_signup = False  # already on the list
        logger.debug("waitlist duplicate email={}", payload.email)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("waitlist insert failed: {}", exc)
        raise HTTPException(status_code=500, detail="storage error")

    # Best-effort welcome email (no-op when SMTP isn't configured).
    if new_signup and smtp_enabled():
        try:
            subject, text, html = waitlist_welcome(payload.email, locale=locale)
            send_email(to=payload.email, subject=subject, text=text, html=html)
        except Exception as exc:  # noqa: BLE001
            logger.warning("waitlist welcome email failed: {}", exc)

    count = db.scalar(select(func.count()).select_from(WaitlistEntry)) or 0
    logger.info("waitlist += {} (total={})", payload.email, count)
    return WaitlistOut(ok=True, count=int(count))


@router.get("/count")
async def waitlist_count(db: Session = Depends(get_session)) -> dict[str, int]:
    _backfill_jsonl_once(db)
    count = db.scalar(select(func.count()).select_from(WaitlistEntry)) or 0
    return {"count": int(count)}
