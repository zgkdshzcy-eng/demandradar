"""Weekly digest generator.

Pulls top-scored PainPoints from the past 7 days, renders a Jinja2 markdown
template, persists into `weekly_reports`. Free preview is the first 3 items;
full content is gated by subscription (D11).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Template
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.cluster import Cluster
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal
from app.models.weekly_report import WeeklyReport

TEMPLATE_PATH = Path(__file__).resolve().parent / "weekly_template.md"

DEFAULT_TOP_N = 20
PREVIEW_TOP_N = 3


@dataclass
class WeeklyStats:
    issue_no: int
    inserted: bool
    items: int

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _load_template() -> Template:
    return Template(TEMPLATE_PATH.read_text(encoding="utf-8"))


def _next_issue_no(db: Session) -> int:
    last = db.scalar(select(func.max(WeeklyReport.issue_no)))
    return int(last or 0) + 1


def _collect_evidence(db: Session, pp: PainPoint, *, limit: int = 3) -> list[dict]:
    ids = (pp.source_signal_ids or [])[:limit]
    if not ids:
        return []
    sigs: list[RawSignal] = list(
        db.execute(select(RawSignal).where(RawSignal.id.in_(ids))).scalars()
    )
    return [
        {
            "source": s.source,
            "title": s.title,
            "url": s.url,
            "text": s.text,
        }
        for s in sigs
    ]


def _build_context(
    db: Session,
    *,
    items_limit: int,
    period_start: datetime,
    period_end: datetime,
    issue_no: int,
) -> tuple[dict, list[int]]:
    rows: list[PainPoint] = list(
        db.execute(
            select(PainPoint)
            .where(PainPoint.total_score.is_not(None))
            .where(PainPoint.created_at >= period_start)
            .where(PainPoint.created_at < period_end)
            .order_by(desc(PainPoint.total_score), desc(PainPoint.created_at))
            .limit(items_limit)
        ).scalars()
    )

    items_data: list[dict] = []
    pp_ids: list[int] = []
    for pp in rows:
        pp_ids.append(pp.id)
        items_data.append(
            {
                "id": pp.id,
                "pain": pp.pain,
                "scenario": pp.scenario,
                "target_user": pp.target_user,
                "frequency_signal": pp.frequency_signal,
                "willingness_to_pay_signal": pp.willingness_to_pay_signal,
                "total_score": round(pp.total_score or 0, 1),
                "go_no_go": pp.go_no_go or "watch",
                "rationale": pp.rationale,
                "evidence": _collect_evidence(db, pp),
            }
        )

    # Aggregate stats over the period.
    raw_count = (
        db.scalar(
            select(func.count())
            .select_from(RawSignal)
            .where(RawSignal.collected_at >= period_start)
            .where(RawSignal.collected_at < period_end)
        )
        or 0
    )
    by_source = list(
        db.execute(
            select(RawSignal.source, func.count())
            .where(RawSignal.collected_at >= period_start)
            .where(RawSignal.collected_at < period_end)
            .group_by(RawSignal.source)
            .order_by(desc(func.count()))
        ).all()
    )
    cluster_count = (
        db.scalar(
            select(func.count())
            .select_from(Cluster)
            .where(Cluster.created_at >= period_start)
            .where(Cluster.created_at < period_end)
        )
        or 0
    )
    new_go = sum(1 for it in items_data if it["go_no_go"] == "go")
    strong_wtp = sum(1 for it in items_data if it["willingness_to_pay_signal"] == "strong")
    avg_score = (
        round(sum(it["total_score"] for it in items_data) / len(items_data), 1)
        if items_data
        else 0
    )
    unique_clusters = len({pp.cluster_id for pp in rows if pp.cluster_id is not None})

    highlight = ""
    if items_data:
        top = items_data[0]
        highlight = f"{top['pain']}（总分 {top['total_score']}）"

    title = f"独立开发者需求雷达 · 第 {issue_no} 期"

    ctx = {
        "title": title,
        "issue_no": issue_no,
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": period_end.strftime("%Y-%m-%d"),
        "items": items_data,
        "source_count": len(by_source),
        "raw_count": int(raw_count),
        "cluster_count": int(cluster_count),
        "unique_clusters": unique_clusters,
        "new_go_count": new_go,
        "avg_score": avg_score,
        "strong_wtp_count": strong_wtp,
        "highlight": highlight,
        "source_breakdown": [(src, int(n)) for src, n in by_source],
    }
    return ctx, pp_ids


def _build_preview(ctx: dict, n: int = PREVIEW_TOP_N) -> str:
    """Cheap preview: first 3 items only, no full evidence chain."""
    preview_ctx = dict(ctx)
    preview_ctx["items"] = ctx["items"][:n]
    preview_ctx["title"] = ctx["title"] + "（免费试读）"
    return _load_template().render(**preview_ctx)


def generate_weekly(
    db: Session,
    *,
    items_limit: int = DEFAULT_TOP_N,
    period_days: int = 7,
    end: datetime | None = None,
) -> WeeklyStats:
    """Generate (or skip if already exists for current period) one weekly issue."""
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(days=period_days)

    # Idempotency: if any report covers an end >= today, skip.
    existing = db.scalar(
        select(WeeklyReport)
        .where(WeeklyReport.period_end >= start)
        .order_by(desc(WeeklyReport.period_end))
        .limit(1)
    )
    if existing is not None and existing.period_end.date() == end.date():
        logger.info("weekly: issue #{} already exists for today", existing.issue_no)
        return WeeklyStats(issue_no=existing.issue_no, inserted=False, items=len(existing.pain_point_ids or []))

    issue_no = _next_issue_no(db)
    ctx, pp_ids = _build_context(
        db,
        items_limit=items_limit,
        period_start=start,
        period_end=end,
        issue_no=issue_no,
    )

    full = _load_template().render(**ctx)
    preview = _build_preview(ctx)

    report = WeeklyReport(
        issue_no=issue_no,
        title=ctx["title"],
        period_start=start,
        period_end=end,
        markdown_full=full,
        markdown_preview=preview,
        pain_point_ids=pp_ids,
        status="published",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info("weekly: issue #{} generated, {} items", issue_no, len(pp_ids))
    return WeeklyStats(issue_no=issue_no, inserted=True, items=len(pp_ids))
