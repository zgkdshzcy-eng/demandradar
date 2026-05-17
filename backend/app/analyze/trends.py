"""Cross-period trend analytics.

We derive heat per (painpoint, ISO-week) from the raw_signal -> cluster ->
pain_point join. Computed on-the-fly so we don't need a new persisted table;
the calls are cheap because they pull only `(cluster_id, posted_at)` columns
into Python and bucket there.

Public surface:

- `weekly_heat(db, weeks=6)`        -> list[PainHeat]
  Per-painpoint week-bucket counts.

- `top_movers(db, lookback_weeks=2)` -> list[Mover]
  Painpoints whose this-week signal count is up most relative to last week.

- `evidence_timeline(db, painpoint_id, limit=80)` -> list[EvidencePoint]
  Chronological raw signals tied to one painpoint, ready for a timeline UI.

- `source_breakdown(db, since_days=30)` -> dict[source -> count]
  Used to show a "where signals came from" donut on /insights.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal


# ---------- helpers ----------

def _iso_week_start(d: datetime) -> datetime:
    """Monday 00:00 UTC of the ISO week containing `d`."""
    d = d.astimezone(timezone.utc)
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------- weekly heat ----------

@dataclass
class WeekBucket:
    week_start: datetime
    count: int


@dataclass
class PainHeat:
    pain_point_id: int
    pain: str
    target_user: str | None
    total_score: float | None
    go_no_go: str | None
    weeks: list[WeekBucket] = field(default_factory=list)

    def total(self) -> int:
        return sum(w.count for w in self.weeks)


def weekly_heat(db: Session, *, weeks: int = 6) -> list[PainHeat]:
    """Return per-painpoint heat across the most recent `weeks` ISO weeks.

    Painpoints that scored zero signals in the window are skipped so callers
    can iterate without filtering.
    """
    if weeks < 1:
        return []
    end = _iso_week_start(_now()) + timedelta(days=7)  # exclusive upper bound
    start = end - timedelta(weeks=weeks)

    # Pull (pp.id, rs.posted_at) for raw signals tied via cluster.
    rows: Iterable[tuple[int, str | None, str | None, float | None, str | None, datetime]] = db.execute(
        select(
            PainPoint.id,
            PainPoint.pain,
            PainPoint.target_user,
            PainPoint.total_score,
            PainPoint.go_no_go,
            RawSignal.posted_at,
        )
        .join(RawSignal, RawSignal.cluster_id == PainPoint.cluster_id)
        .where(PainPoint.cluster_id.is_not(None))
        .where(RawSignal.posted_at.is_not(None))
        .where(RawSignal.posted_at >= start)
        .where(RawSignal.posted_at < end)
    ).all()

    # Build [pp_id -> meta], [pp_id -> {week_start -> count}].
    meta: dict[int, tuple[str, str | None, float | None, str | None]] = {}
    bucket: dict[int, dict[datetime, int]] = defaultdict(lambda: defaultdict(int))
    for pp_id, pain, target, score, gng, posted in rows:
        if pp_id not in meta:
            meta[pp_id] = (pain, target, score, gng)
        bucket[pp_id][_iso_week_start(posted)] += 1

    # Materialise the week column so all painpoints share the same x-axis.
    week_starts = [
        end - timedelta(days=7 * (i + 1)) for i in reversed(range(weeks))
    ]

    out: list[PainHeat] = []
    for pp_id, (pain, target, score, gng) in meta.items():
        weeks_list = [
            WeekBucket(week_start=ws, count=int(bucket[pp_id].get(ws, 0)))
            for ws in week_starts
        ]
        if all(w.count == 0 for w in weeks_list):
            continue
        out.append(
            PainHeat(
                pain_point_id=pp_id,
                pain=pain,
                target_user=target,
                total_score=score,
                go_no_go=gng,
                weeks=weeks_list,
            )
        )
    out.sort(key=lambda x: x.total(), reverse=True)
    return out


# ---------- top movers ----------

@dataclass
class Mover:
    pain_point_id: int
    pain: str
    target_user: str | None
    total_score: float | None
    this_week: int
    last_week: int
    delta: int
    delta_pct: float  # +inf when last_week == 0 and this_week > 0


def _safe_pct(this_w: int, last_w: int) -> float:
    if last_w == 0:
        return float("inf") if this_w > 0 else 0.0
    return (this_w - last_w) / last_w * 100.0


def top_movers(
    db: Session,
    *,
    lookback_weeks: int = 2,
    min_signals: int = 3,
    limit: int = 20,
) -> list[Mover]:
    """Painpoints with the largest WoW heat increase.

    We require at least `min_signals` total in this+last week to filter out
    noise (a 1->2 jump shouldn't dominate the leaderboard).
    """
    heats = weekly_heat(db, weeks=lookback_weeks)
    movers: list[Mover] = []
    for h in heats:
        if len(h.weeks) < 2:
            continue
        last = h.weeks[-2].count
        this = h.weeks[-1].count
        if (this + last) < min_signals:
            continue
        movers.append(
            Mover(
                pain_point_id=h.pain_point_id,
                pain=h.pain,
                target_user=h.target_user,
                total_score=h.total_score,
                this_week=this,
                last_week=last,
                delta=this - last,
                delta_pct=_safe_pct(this, last),
            )
        )
    # Sort by delta desc (then by absolute this-week count for ties).
    movers.sort(key=lambda m: (m.delta, m.this_week), reverse=True)
    return movers[:limit]


# ---------- evidence timeline ----------

@dataclass
class EvidencePoint:
    raw_signal_id: int
    source: str
    posted_at: datetime
    title: str | None
    text: str
    url: str | None
    score: int


def evidence_timeline(
    db: Session, painpoint_id: int, *, limit: int = 80
) -> list[EvidencePoint]:
    pp = db.get(PainPoint, painpoint_id)
    if pp is None or pp.cluster_id is None:
        return []
    rows = db.execute(
        select(
            RawSignal.id,
            RawSignal.source,
            RawSignal.posted_at,
            RawSignal.title,
            RawSignal.text,
            RawSignal.url,
            RawSignal.score,
        )
        .where(RawSignal.cluster_id == pp.cluster_id)
        .where(RawSignal.posted_at.is_not(None))
        .order_by(RawSignal.posted_at.desc())
        .limit(limit)
    ).all()
    out: list[EvidencePoint] = []
    for rid, src, posted, title, text, url, score in rows:
        out.append(
            EvidencePoint(
                raw_signal_id=int(rid),
                source=str(src),
                posted_at=posted,
                title=title,
                text=text or "",
                url=url,
                score=int(score or 0),
            )
        )
    return out


# ---------- source breakdown ----------

def source_breakdown(db: Session, *, since_days: int = 30) -> dict[str, int]:
    cutoff = _now() - timedelta(days=since_days)
    rows = db.execute(
        select(RawSignal.source, func.count())
        .where(RawSignal.collected_at >= cutoff)
        .group_by(RawSignal.source)
    ).all()
    return {str(s): int(n) for s, n in rows}


__all__ = [
    "EvidencePoint",
    "Mover",
    "PainHeat",
    "WeekBucket",
    "evidence_timeline",
    "source_breakdown",
    "top_movers",
    "weekly_heat",
]
