"""10-dimension scoring of PainPoints via LLM JSON.

For each PainPoint with `total_score IS NULL`, render `prompts/scoring.md`,
call LLM, parse JSON, fill the 10 score columns + total_score + rationale +
go_no_go. We also recompute the local weighted total as a safety net (LLM
sometimes returns wrong arithmetic).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzer.prompts import load_prompt, render
from app.core.llm import llm
from app.core.logging import logger
from app.models.pain_point import PainPoint

# Default weights (must match prompts/scoring.md description).
WEIGHTS: dict[str, float] = {
    "pain_intensity": 0.15,
    "frequency": 0.10,
    "willingness_to_pay": 0.20,
    "reach_difficulty": 0.05,
    "dev_difficulty": 0.10,
    "competition": 0.10,
    "differentiation": 0.10,
    "automation_potential": 0.08,
    "virality": 0.07,
    "retention": 0.05,
}
SCORE_COLUMNS: tuple[str, ...] = tuple(WEIGHTS.keys())
GO_VALUES = {"go", "watch", "drop"}


@dataclass
class ScoreStats:
    seen: int = 0
    scored: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _clip(v: object) -> int | None:
    try:
        i = int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return max(1, min(5, i))


def _weighted_total(scores: dict[str, int | None]) -> float:
    total = 0.0
    weight_sum = 0.0
    for k, w in WEIGHTS.items():
        s = scores.get(k)
        if s is None:
            continue
        total += s * w
        weight_sum += w
    if weight_sum == 0:
        return 0.0
    # Normalize to 0-100 scale (each dim is 1-5; max raw weighted = 5 * sum_w).
    return round(total / weight_sum * 20, 2)


def _build_pain_json(pp: PainPoint) -> str:
    return json.dumps(
        {
            "pain": pp.pain,
            "scenario": pp.scenario,
            "target_user": pp.target_user,
            "frequency_signal": pp.frequency_signal,
            "emotion": pp.emotion,
            "willingness_to_pay_signal": pp.willingness_to_pay_signal,
            "diy_workaround": pp.diy_workaround,
            "evidence_quote": pp.evidence_quote,
        },
        ensure_ascii=False,
    )


async def score_one(db: Session, pp: PainPoint) -> bool:
    """Score one PainPoint in-place. Returns True on success, False on skip."""
    system, user_tpl = load_prompt("scoring")
    prompt = render(user_tpl, PAIN_JSON=_build_pain_json(pp))

    try:
        result = await llm.complete_json(
            prompt, system=system, temperature=0.1, task="score", purpose="score"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("score LLM failed pp={}: {}", pp.id, exc)
        return False

    if not isinstance(result, dict):
        # Tolerate {"score": {...}} wrappers
        if isinstance(result, list) and result:
            result = result[0]
        else:
            logger.warning("score: unexpected LLM shape for pp={}", pp.id)
            return False

    scores: dict[str, int | None] = {}
    for col in SCORE_COLUMNS:
        scores[col] = _clip(result.get(col))
        setattr(pp, col, scores[col])

    # Trust local arithmetic; ignore LLM's total to avoid drift.
    pp.total_score = _weighted_total(scores)

    rationale = result.get("rationale")
    if isinstance(rationale, str):
        pp.rationale = rationale[:1000]

    go = str(result.get("go_no_go") or "").strip().lower()
    if go in GO_VALUES:
        pp.go_no_go = go
    else:
        # Auto-derive go_no_go from total_score if LLM didn't comply.
        if pp.total_score >= 70:
            pp.go_no_go = "go"
        elif pp.total_score >= 50:
            pp.go_no_go = "watch"
        else:
            pp.go_no_go = "drop"

    return True


async def run_score(db: Session, *, limit: int = 30) -> ScoreStats:
    """Score up to `limit` un-scored PainPoints."""
    stats = ScoreStats()
    rows: list[PainPoint] = list(
        db.execute(
            select(PainPoint)
            .where(PainPoint.total_score.is_(None))
            .order_by(PainPoint.created_at.desc())
            .limit(limit)
        ).scalars()
    )
    stats.seen = len(rows)
    if not rows:
        return stats

    for pp in rows:
        try:
            ok = await score_one(db, pp)
            if ok:
                stats.scored += 1
            else:
                stats.skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.exception("score pp={} crashed: {}", pp.id, exc)

    db.commit()
    logger.info("score done: {}", stats.as_dict())
    return stats
