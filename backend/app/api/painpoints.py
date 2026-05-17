"""Public API for browsing PainPoints (the radar feed).

Authentication is intentionally absent in MVP - we expose the feed as the
free funnel. Day 11 adds gating for the full weekly report / brief.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.cluster import Cluster
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal

router = APIRouter(prefix="/api/painpoints", tags=["painpoints"])


class EvidenceOut(BaseModel):
    id: int
    source: str
    url: str | None
    title: str | None
    quote: str


class PainPointOut(BaseModel):
    id: int
    pain: str
    scenario: str | None = None
    target_user: str | None = None
    frequency_signal: str
    emotion: str
    willingness_to_pay_signal: str
    total_score: float | None = None
    go_no_go: str | None = None
    rationale: str | None = None
    cluster_id: int | None = None
    cluster_label: str | None = None
    scores: dict[str, int | None] | None = None
    created_at: datetime
    evidence: list[EvidenceOut] = Field(default_factory=list)


class PainPointListOut(BaseModel):
    total: int
    items: list[PainPointOut]


_SCORE_COLS = (
    "pain_intensity",
    "frequency",
    "willingness_to_pay",
    "reach_difficulty",
    "dev_difficulty",
    "competition",
    "differentiation",
    "automation_potential",
    "virality",
    "retention",
)


def _to_out(pp: PainPoint, cluster_label: str | None, evidence: list[EvidenceOut]) -> PainPointOut:
    return PainPointOut(
        id=pp.id,
        pain=pp.pain,
        scenario=pp.scenario,
        target_user=pp.target_user,
        frequency_signal=pp.frequency_signal,
        emotion=pp.emotion,
        willingness_to_pay_signal=pp.willingness_to_pay_signal,
        total_score=float(pp.total_score) if pp.total_score is not None else None,
        go_no_go=pp.go_no_go,
        rationale=pp.rationale,
        cluster_id=pp.cluster_id,
        cluster_label=cluster_label,
        scores={col: getattr(pp, col) for col in _SCORE_COLS},
        created_at=pp.created_at,
        evidence=evidence,
    )


def _load_evidence(db: Session, pp: PainPoint, *, max_items: int = 5) -> list[EvidenceOut]:
    ids = pp.source_signal_ids or []
    if not ids:
        return []
    sigs: list[RawSignal] = list(
        db.execute(
            select(RawSignal).where(RawSignal.id.in_(ids[:max_items]))
        ).scalars()
    )
    out: list[EvidenceOut] = []
    quote = (pp.evidence_quote or "").strip()
    for s in sigs:
        out.append(
            EvidenceOut(
                id=s.id,
                source=s.source,
                url=s.url,
                title=s.title,
                quote=quote or (s.text[:80] if s.text else ""),
            )
        )
    return out


@router.get("", response_model=PainPointListOut)
async def list_painpoints(
    db: Session = Depends(get_session),
    go_no_go: str | None = Query(None, pattern="^(go|watch|drop)$"),
    min_score: float | None = Query(None, ge=0, le=100),
    lang: str | None = Query(None, max_length=8),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query("score", pattern="^(score|recent)$"),
) -> PainPointListOut:
    q = select(PainPoint).where(PainPoint.total_score.is_not(None))
    if go_no_go:
        q = q.where(PainPoint.go_no_go == go_no_go)
    if min_score is not None:
        q = q.where(PainPoint.total_score >= min_score)
    if lang:
        # Filter via cluster.lang_primary
        q = q.join(Cluster, PainPoint.cluster_id == Cluster.id).where(
            Cluster.lang_primary == lang
        )

    # Total
    total = db.scalar(
        select(func.count()).select_from(q.subquery())
    ) or 0

    if order == "score":
        q = q.order_by(desc(PainPoint.total_score), desc(PainPoint.created_at))
    else:
        q = q.order_by(desc(PainPoint.created_at))

    rows: list[PainPoint] = list(db.execute(q.limit(limit).offset(offset)).scalars())

    # Cluster labels lookup (one round-trip)
    cluster_ids = [r.cluster_id for r in rows if r.cluster_id]
    label_map: dict[int, str] = {}
    if cluster_ids:
        for cid, label in db.execute(
            select(Cluster.id, Cluster.label).where(Cluster.id.in_(cluster_ids))
        ).all():
            label_map[cid] = label

    items: list[PainPointOut] = []
    for pp in rows:
        items.append(
            _to_out(
                pp,
                cluster_label=label_map.get(pp.cluster_id) if pp.cluster_id else None,
                evidence=_load_evidence(db, pp),
            )
        )
    return PainPointListOut(total=int(total), items=items)


@router.get("/top", response_model=list[PainPointOut])
async def top_painpoints(
    db: Session = Depends(get_session),
    limit: int = Query(20, ge=1, le=50),
) -> list[PainPointOut]:
    """Curated top list: go-rated, scored, ordered by total_score desc."""
    rows: list[PainPoint] = list(
        db.execute(
            select(PainPoint)
            .where(PainPoint.total_score.is_not(None))
            .where(PainPoint.go_no_go == "go")
            .order_by(desc(PainPoint.total_score))
            .limit(limit)
        ).scalars()
    )
    cluster_ids = [r.cluster_id for r in rows if r.cluster_id]
    label_map: dict[int, str] = {}
    if cluster_ids:
        for cid, label in db.execute(
            select(Cluster.id, Cluster.label).where(Cluster.id.in_(cluster_ids))
        ).all():
            label_map[cid] = label
    return [
        _to_out(
            pp,
            cluster_label=label_map.get(pp.cluster_id) if pp.cluster_id else None,
            evidence=_load_evidence(db, pp),
        )
        for pp in rows
    ]


@router.get("/{pain_id}", response_model=PainPointOut)
async def get_painpoint(pain_id: int, db: Session = Depends(get_session)) -> PainPointOut:
    pp = db.get(PainPoint, pain_id)
    if pp is None:
        raise HTTPException(status_code=404, detail="not found")
    cluster_label: str | None = None
    if pp.cluster_id:
        cluster_label = db.scalar(
            select(Cluster.label).where(Cluster.id == pp.cluster_id)
        )
    return _to_out(pp, cluster_label=cluster_label, evidence=_load_evidence(db, pp))


@router.get("/-/stats")
async def stats(db: Session = Depends(get_session)) -> dict[str, Any]:
    """Aggregate counts: total, scored, by go_no_go, average score."""
    total = db.scalar(select(func.count()).select_from(PainPoint)) or 0
    scored = db.scalar(
        select(func.count()).select_from(PainPoint).where(
            PainPoint.total_score.is_not(None)
        )
    ) or 0
    by_go = dict(
        db.execute(
            select(PainPoint.go_no_go, func.count())
            .where(PainPoint.total_score.is_not(None))
            .group_by(PainPoint.go_no_go)
        ).all()
    )
    avg_score = db.scalar(
        select(func.avg(PainPoint.total_score)).where(PainPoint.total_score.is_not(None))
    )
    return {
        "total": int(total),
        "scored": int(scored),
        "by_go_no_go": {k or "unknown": int(v) for k, v in by_go.items()},
        "avg_score": float(avg_score) if avg_score is not None else None,
    }
