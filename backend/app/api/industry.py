"""Industry pain ranking: aggregate painpoints by industry/category for
the industry benchmarking page.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.pain_point import PainPoint

router = APIRouter(prefix="/api/industry", tags=["industry"])


class IndustryRanking(BaseModel):
    industry: str
    painpoint_count: int
    avg_score: float
    top_pain: str
    top_pain_score: float | None


@router.get("/ranking", response_model=list[IndustryRanking])
def industry_ranking(
    db: Session = Depends(get_session),
    limit: int = Query(20, ge=1, le=50),
) -> list[IndustryRanking]:
    """Return industry rankings: for each industry, count painpoints and avg score."""
    rows = list(
        db.execute(
            select(
                PainPoint.industry,
                func.count().label("cnt"),
                func.avg(PainPoint.total_score).label("avg_score"),
            )
            .where(PainPoint.industry.is_not(None), PainPoint.total_score.is_not(None))
            .group_by(PainPoint.industry)
            .order_by(func.avg(PainPoint.total_score).desc())
            .limit(limit)
        ).all()
    )

    result: list[IndustryRanking] = []
    for industry, cnt, avg_score in rows:
        top = db.execute(
            select(PainPoint)
            .where(PainPoint.industry == industry, PainPoint.total_score.is_not(None))
            .order_by(PainPoint.total_score.desc())
            .limit(1)
        ).scalar()
        result.append(IndustryRanking(
            industry=industry,
            painpoint_count=cnt,
            avg_score=round(float(avg_score), 1),
            top_pain=top.pain if top else "",
            top_pain_score=float(top.total_score) if top and top.total_score else None,
        ))

    return result


class IndustryDetail(BaseModel):
    industry: str
    painpoints: list["PainPointSummary"]


class PainPointSummary(BaseModel):
    id: int
    pain: str
    total_score: float | None
    target_user: str | None
    go_no_go: str | None


@router.get("/{industry}", response_model=IndustryDetail)
def industry_detail(
    industry: str,
    db: Session = Depends(get_session),
    limit: int = Query(30, ge=1, le=100),
) -> IndustryDetail:
    rows = list(
        db.execute(
            select(PainPoint)
            .where(PainPoint.industry == industry, PainPoint.total_score.is_not(None))
            .order_by(PainPoint.total_score.desc())
            .limit(limit)
        ).scalars()
    )
    return IndustryDetail(
        industry=industry,
        painpoints=[
            PainPointSummary(
                id=pp.id,
                pain=pp.pain,
                total_score=float(pp.total_score) if pp.total_score else None,
                target_user=pp.target_user,
                go_no_go=pp.go_no_go,
            )
            for pp in rows
        ],
    )
