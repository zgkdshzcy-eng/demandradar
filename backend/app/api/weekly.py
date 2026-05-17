"""Weekly digest API.

- /api/weekly            list (preview only)
- /api/weekly/latest     latest issue (preview)
- /api/weekly/{issue_no} detail; markdown_full requires unlock token until D11
- /api/weekly/{issue_no}/html
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
from app.models.weekly_report import WeeklyReport
from app.report.pdf import md_to_html_doc

router = APIRouter(prefix="/api/weekly", tags=["weekly"])


class WeeklySummary(BaseModel):
    id: int
    issue_no: int
    title: str
    period_start: datetime
    period_end: datetime
    status: str
    items: int
    created_at: datetime


class WeeklyDetail(WeeklySummary):
    markdown_preview: str
    markdown_full: str | None = None
    unlocked: bool


def _to_summary(r: WeeklyReport) -> WeeklySummary:
    return WeeklySummary(
        id=r.id,
        issue_no=r.issue_no,
        title=r.title,
        period_start=r.period_start,
        period_end=r.period_end,
        status=r.status,
        items=len(r.pain_point_ids or []),
        created_at=r.created_at,
    )


def _is_unlocked(ent: Entitlement) -> bool:
    return ent.can_read_weekly()


@router.get("", response_model=list[WeeklySummary])
async def list_weekly(
    db: Session = Depends(get_session),
    limit: int = 12,
    offset: int = 0,
) -> list[WeeklySummary]:
    rows: list[WeeklyReport] = list(
        db.execute(
            select(WeeklyReport)
            .order_by(desc(WeeklyReport.issue_no))
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    return [_to_summary(r) for r in rows]


@router.get("/latest", response_model=WeeklyDetail)
async def latest_weekly(
    db: Session = Depends(get_session),
    ent: Entitlement = Depends(current_entitlement),
) -> WeeklyDetail:
    r = db.scalar(
        select(WeeklyReport).order_by(desc(WeeklyReport.issue_no)).limit(1)
    )
    if r is None:
        raise HTTPException(status_code=404, detail="no issues yet")
    return _detail(r, ent)


@router.get("/{issue_no}", response_model=WeeklyDetail)
async def get_weekly(
    issue_no: int,
    db: Session = Depends(get_session),
    ent: Entitlement = Depends(current_entitlement),
) -> WeeklyDetail:
    r = db.scalar(select(WeeklyReport).where(WeeklyReport.issue_no == issue_no))
    if r is None:
        raise HTTPException(status_code=404, detail="not found")
    return _detail(r, ent)


def _detail(r: WeeklyReport, ent: Entitlement) -> WeeklyDetail:
    unlocked = _is_unlocked(ent)
    base = _to_summary(r).model_dump()
    return WeeklyDetail(
        **base,
        markdown_preview=r.markdown_preview,
        markdown_full=r.markdown_full if unlocked else None,
        unlocked=unlocked,
    )


@router.get("/{issue_no}/html")
async def get_weekly_html(
    issue_no: int,
    db: Session = Depends(get_session),
    ent: Entitlement = Depends(current_entitlement),
) -> Response:
    r = db.scalar(select(WeeklyReport).where(WeeklyReport.issue_no == issue_no))
    if r is None:
        raise HTTPException(status_code=404, detail="not found")
    if not _is_unlocked(ent):
        # Render preview only when locked
        html = md_to_html_doc(r.markdown_preview, title=r.title)
    else:
        html = md_to_html_doc(r.markdown_full, title=r.title)
    return Response(content=html, media_type="text/html; charset=utf-8")
