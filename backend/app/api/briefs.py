"""Briefs API: list, detail (json/markdown/html/pdf).

Visibility:
- 'public' briefs: anyone can read
- 'paid' briefs:   list returns metadata + locked preview (first ~200 chars);
                   full content returns 402-style hint until D11 subscription.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.deps import current_entitlement
from app.core.entitlement import Entitlement
from app.db.session import get_session
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.report.pdf import PDF_AVAILABLE, md_to_html_doc, md_to_pdf_bytes

router = APIRouter(prefix="/api/briefs", tags=["briefs"])

PREVIEW_CHARS = 240


class BriefSummary(BaseModel):
    id: int
    pain_point_id: int
    title: str
    visibility: str
    version: int
    total_score: float | None = None
    pain: str | None = None
    preview: str
    created_at: datetime


class BriefListOut(BaseModel):
    total: int
    items: list[BriefSummary]


def _make_preview(markdown: str) -> str:
    text = markdown.strip()
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[:PREVIEW_CHARS].rstrip() + " ..."


def _summarize(b: Brief, pp: PainPoint | None) -> BriefSummary:
    return BriefSummary(
        id=b.id,
        pain_point_id=b.pain_point_id,
        title=b.title,
        visibility=b.visibility,
        version=b.version,
        total_score=float(pp.total_score) if pp and pp.total_score is not None else None,
        pain=pp.pain if pp else None,
        preview=_make_preview(b.markdown),
        created_at=b.created_at,
    )


def _is_unlocked(b: Brief, ent: Entitlement) -> bool:
    """public briefs are always readable; paid briefs require entitlement.

    Entitlement is derived from the active Subscription rows (D10) but still
    honours `X-Unlock-Token == APP_SECRET_KEY` as an admin master override.
    """
    if b.visibility == "public":
        return True
    return ent.can_read_brief(b.id)


@router.get("", response_model=BriefListOut)
async def list_briefs(
    db: Session = Depends(get_session),
    limit: int = 20,
    offset: int = 0,
) -> BriefListOut:
    total = db.scalar(select(func.count()).select_from(Brief)) or 0
    rows: list[Brief] = list(
        db.execute(
            select(Brief).order_by(desc(Brief.created_at)).limit(limit).offset(offset)
        ).scalars()
    )
    pp_ids = [b.pain_point_id for b in rows]
    pp_map: dict[int, PainPoint] = {}
    if pp_ids:
        for pp in db.execute(
            select(PainPoint).where(PainPoint.id.in_(pp_ids))
        ).scalars():
            pp_map[pp.id] = pp
    items = [_summarize(b, pp_map.get(b.pain_point_id)) for b in rows]
    return BriefListOut(total=int(total), items=items)


@router.get("/{brief_id}")
async def get_brief(
    brief_id: int,
    db: Session = Depends(get_session),
    ent: Entitlement = Depends(current_entitlement),
) -> dict:
    b = db.get(Brief, brief_id)
    if b is None:
        raise HTTPException(status_code=404, detail="not found")
    pp = db.get(PainPoint, b.pain_point_id)

    summary = _summarize(b, pp).model_dump()
    summary["unlocked"] = _is_unlocked(b, ent)
    if summary["unlocked"]:
        summary["markdown"] = b.markdown
    return summary


@router.get("/{brief_id}/markdown")
async def get_brief_markdown(
    brief_id: int,
    db: Session = Depends(get_session),
    ent: Entitlement = Depends(current_entitlement),
) -> Response:
    b = db.get(Brief, brief_id)
    if b is None:
        raise HTTPException(status_code=404, detail="not found")
    if not _is_unlocked(b, ent):
        raise HTTPException(status_code=402, detail="payment required")
    return Response(content=b.markdown, media_type="text/markdown; charset=utf-8")


@router.get("/{brief_id}/html")
async def get_brief_html(
    brief_id: int,
    db: Session = Depends(get_session),
    ent: Entitlement = Depends(current_entitlement),
) -> Response:
    b = db.get(Brief, brief_id)
    if b is None:
        raise HTTPException(status_code=404, detail="not found")
    if not _is_unlocked(b, ent):
        raise HTTPException(status_code=402, detail="payment required")
    html = md_to_html_doc(b.markdown, title=b.title)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/{brief_id}/pdf")
async def get_brief_pdf(
    brief_id: int,
    db: Session = Depends(get_session),
    ent: Entitlement = Depends(current_entitlement),
) -> Response:
    if not PDF_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF rendering unavailable on this server. Use /html or /markdown.",
        )
    b = db.get(Brief, brief_id)
    if b is None:
        raise HTTPException(status_code=404, detail="not found")
    if not _is_unlocked(b, ent):
        raise HTTPException(status_code=402, detail="payment required")
    pdf_bytes = md_to_pdf_bytes(b.markdown, title=b.title)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="brief-{b.id}.pdf"',
        },
    )
