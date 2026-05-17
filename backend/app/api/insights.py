"""D16 Insights API.

Public read-only endpoints powering the /insights page. Three views:

- /api/insights/heat        — per-painpoint week-bucket heat
- /api/insights/movers      — top week-over-week movers
- /api/insights/timeline    — evidence timeline for one painpoint
- /api/insights/sources     — source breakdown for the past N days
- /api/insights/export.csv  — CSV download of any of the above

We do NOT gate these behind paywall — they advertise the system's value to
anonymous browsers (and the underlying signal counts are public anyway).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analyze import trends as ta
from app.db.session import get_session

router = APIRouter(prefix="/api/insights", tags=["insights"])


# ---------- response schemas ----------

class HeatWeek(BaseModel):
    week_start: datetime
    count: int


class HeatRow(BaseModel):
    pain_point_id: int
    pain: str
    target_user: str | None
    total_score: float | None
    go_no_go: str | None
    total: int
    weeks: list[HeatWeek]


class MoverRow(BaseModel):
    pain_point_id: int
    pain: str
    target_user: str | None
    total_score: float | None
    this_week: int
    last_week: int
    delta: int
    delta_pct: float | None  # null when math says +inf (new from zero)


class TimelinePoint(BaseModel):
    raw_signal_id: int
    source: str
    posted_at: datetime
    title: str | None
    text: str
    url: str | None
    score: int


# ---------- endpoints ----------

@router.get("/heat", response_model=list[HeatRow])
def heat(
    weeks: int = Query(6, ge=1, le=26),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> list[HeatRow]:
    rows = ta.weekly_heat(db, weeks=weeks)[:limit]
    return [
        HeatRow(
            pain_point_id=r.pain_point_id,
            pain=r.pain,
            target_user=r.target_user,
            total_score=r.total_score,
            go_no_go=r.go_no_go,
            total=r.total(),
            weeks=[HeatWeek(week_start=w.week_start, count=w.count) for w in r.weeks],
        )
        for r in rows
    ]


@router.get("/movers", response_model=list[MoverRow])
def movers(
    limit: int = Query(20, ge=1, le=100),
    min_signals: int = Query(3, ge=1, le=50),
    db: Session = Depends(get_session),
) -> list[MoverRow]:
    rows = ta.top_movers(db, lookback_weeks=2, min_signals=min_signals, limit=limit)
    return [
        MoverRow(
            pain_point_id=r.pain_point_id,
            pain=r.pain,
            target_user=r.target_user,
            total_score=r.total_score,
            this_week=r.this_week,
            last_week=r.last_week,
            delta=r.delta,
            delta_pct=None if r.delta_pct == float("inf") else round(r.delta_pct, 1),
        )
        for r in rows
    ]


@router.get("/timeline/{painpoint_id}", response_model=list[TimelinePoint])
def timeline(
    painpoint_id: int,
    limit: int = Query(80, ge=1, le=300),
    db: Session = Depends(get_session),
) -> list[TimelinePoint]:
    rows = ta.evidence_timeline(db, painpoint_id, limit=limit)
    if not rows:
        # Either id unknown or no clustered signals — return empty list (the
        # painpoint detail endpoint already 404s for unknown ids).
        return []
    return [
        TimelinePoint(
            raw_signal_id=r.raw_signal_id,
            source=r.source,
            posted_at=r.posted_at,
            title=r.title,
            text=r.text[:500],
            url=r.url,
            score=r.score,
        )
        for r in rows
    ]


@router.get("/sources")
def sources(
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_session),
) -> dict[str, int]:
    return ta.source_breakdown(db, since_days=days)


# ---------- CSV export ----------

_KIND = Literal["heat", "movers", "timeline"]


def _csv_response(filename: str, rows: list[list], header: list[str]) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.csv")
def export_csv(
    kind: _KIND = Query(...),
    weeks: int = Query(6, ge=1, le=26),
    painpoint_id: int | None = None,
    db: Session = Depends(get_session),
) -> Response:
    if kind == "heat":
        data = ta.weekly_heat(db, weeks=weeks)
        header = (
            ["pain_point_id", "pain", "target_user", "total_score", "go_no_go", "total"]
            + [f"w{i+1}_count" for i in range(weeks)]
        )
        rows: list[list] = []
        for h in data:
            rows.append(
                [
                    h.pain_point_id,
                    h.pain,
                    h.target_user or "",
                    f"{h.total_score:.1f}" if h.total_score is not None else "",
                    h.go_no_go or "",
                    h.total(),
                    *[w.count for w in h.weeks],
                ]
            )
        return _csv_response("painpoint_heat.csv", rows, header)

    if kind == "movers":
        data_m = ta.top_movers(db, lookback_weeks=2, limit=200)
        header = [
            "pain_point_id", "pain", "target_user", "total_score",
            "this_week", "last_week", "delta", "delta_pct",
        ]
        rows = [
            [
                m.pain_point_id, m.pain, m.target_user or "",
                f"{m.total_score:.1f}" if m.total_score is not None else "",
                m.this_week, m.last_week, m.delta,
                "" if m.delta_pct == float("inf") else f"{m.delta_pct:.1f}",
            ]
            for m in data_m
        ]
        return _csv_response("painpoint_movers.csv", rows, header)

    if kind == "timeline":
        if painpoint_id is None:
            raise HTTPException(status_code=400, detail="painpoint_id required for timeline")
        pts = ta.evidence_timeline(db, painpoint_id, limit=300)
        header = ["raw_signal_id", "source", "posted_at", "title", "text", "url", "score"]
        rows = [
            [
                p.raw_signal_id, p.source,
                p.posted_at.isoformat() if p.posted_at else "",
                p.title or "", p.text[:500].replace("\n", " "),
                p.url or "", p.score,
            ]
            for p in pts
        ]
        return _csv_response(f"timeline_{painpoint_id}.csv", rows, header)

    raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")


__all__ = ["router"]
