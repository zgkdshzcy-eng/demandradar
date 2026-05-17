"""Generate the 13-section Project Brief markdown from a scored PainPoint.

Reads `prompts/project_brief.md`, injects the pain JSON / score JSON /
evidence JSON, calls LLM, persists into `briefs` table.

Selection: only PainPoints with `go_no_go == 'go'` and total_score >= 70
qualify by default (the Brief is the high-end paid artifact).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzer.prompts import detect_lang, load_prompt, render
from app.core.llm import llm
from app.core.logging import logger
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal
from app.scorer.score import SCORE_COLUMNS

MAX_EVIDENCE = 8
MAX_QUOTE_CHARS = 200


@dataclass
class BriefStats:
    eligible: int = 0
    generated: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _pain_json(pp: PainPoint) -> str:
    return json.dumps(
        {
            "id": pp.id,
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


def _score_json(pp: PainPoint) -> str:
    return json.dumps(
        {
            **{col: getattr(pp, col) for col in SCORE_COLUMNS},
            "total_score": pp.total_score,
            "go_no_go": pp.go_no_go,
            "rationale": pp.rationale,
        },
        ensure_ascii=False,
    )


def _evidence_json(db: Session, pp: PainPoint) -> str:
    ids = (pp.source_signal_ids or [])[:MAX_EVIDENCE]
    if not ids:
        return "[]"
    sigs: list[RawSignal] = list(
        db.execute(select(RawSignal).where(RawSignal.id.in_(ids))).scalars()
    )
    items = []
    for s in sigs:
        quote = (s.title or s.text or "")[:MAX_QUOTE_CHARS]
        items.append(
            {
                "id": s.id,
                "source": s.source,
                "url": s.url,
                "lang": s.lang,
                "score": s.score,
                "quote": quote,
            }
        )
    return json.dumps(items, ensure_ascii=False)


_TITLE_RE = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _extract_title(markdown: str, fallback: str) -> str:
    """Pick the first heading or first non-empty line as title."""
    m = _TITLE_RE.search(markdown)
    if m:
        return m.group(1).strip()[:255]
    for line in markdown.splitlines():
        if line.strip():
            return line.strip()[:255]
    return fallback[:255]


def _pp_lang(db: Session, pp: PainPoint) -> str:
    """Pick `"zh"` or `"en"` from the painpoint metadata + a sample of its
    evidence quotes. Mirrors the heuristic in `analyzer/extract.py`."""
    sample = " ".join(
        s for s in (pp.pain, pp.scenario, pp.target_user) if s
    )
    if len(sample) < 80:
        # Pull a couple of evidence titles/snippets to bulk up the sniff.
        rows = db.execute(
            select(RawSignal.title, RawSignal.text)
            .where(RawSignal.cluster_id == pp.cluster_id)
            .limit(5)
        ).all()
        for title, text in rows:
            sample += " " + (title or "") + " " + ((text or "")[:160])
    return detect_lang(sample)


async def generate_one(db: Session, pp: PainPoint) -> Brief | None:
    """Generate one Brief for the given PainPoint, persist it, return the row."""
    lang = _pp_lang(db, pp)
    system, user_tpl = load_prompt("project_brief", lang=lang)
    prompt = render(
        user_tpl,
        PAIN_JSON=_pain_json(pp),
        SCORE_JSON=_score_json(pp),
        EVIDENCE_JSON=_evidence_json(db, pp),
    )

    try:
        # Briefs benefit from higher temperature for variety, but cap at 0.4
        # to stay grounded in evidence.
        markdown = await llm.complete(
            prompt, system=system, temperature=0.35, max_tokens=4096,
            task="brief", purpose="brief",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("brief LLM failed pp={}: {}", pp.id, exc)
        return None

    markdown = (markdown or "").strip()
    if len(markdown) < 200:
        logger.warning("brief too short for pp={} (len={})", pp.id, len(markdown))
        return None

    title = _extract_title(markdown, fallback=pp.pain)

    brief = Brief(
        pain_point_id=pp.id,
        title=title,
        markdown=markdown,
        visibility="paid",
        version=1,
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


async def run_briefs(
    db: Session,
    *,
    max_briefs: int = 5,
    min_score: float = 70.0,
) -> BriefStats:
    """Generate briefs for high-scored PainPoints that don't yet have one."""
    stats = BriefStats()

    sub = select(Brief.pain_point_id).distinct()
    rows: list[PainPoint] = list(
        db.execute(
            select(PainPoint)
            .where(PainPoint.total_score.is_not(None))
            .where(PainPoint.total_score >= min_score)
            .where(PainPoint.go_no_go == "go")
            .where(PainPoint.id.not_in(sub))
            .order_by(PainPoint.total_score.desc())
            .limit(max_briefs)
        ).scalars()
    )
    stats.eligible = len(rows)
    if not rows:
        return stats

    for pp in rows:
        try:
            brief = await generate_one(db, pp)
            if brief is not None:
                stats.generated += 1
                # D15: queue a PH candidate (status=manual) for the admin to
                # copy/paste. Best-effort: never fail the brief job over this.
                try:
                    from app.notify.producthunt import enqueue_for_brief
                    enqueue_for_brief(db, brief)
                    db.commit()
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    logger.warning("ph enqueue failed for brief={}: {}", brief.id, exc)
                # D19: auto-tweet high-score briefs (status=manual when X disabled).
                try:
                    from app.notify.twitter import enqueue_brief_post
                    enqueue_brief_post(db, brief)
                    db.commit()
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    logger.warning(
                        "tweet enqueue failed for brief={}: {}", brief.id, exc
                    )
                # Mirror to Weibo (status=manual when WEIBO_ENABLED=false).
                try:
                    from app.notify.weibo import (
                        enqueue_brief_post as enqueue_weibo_brief,
                    )
                    enqueue_weibo_brief(db, brief)
                    db.commit()
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    logger.warning(
                        "weibo enqueue failed for brief={}: {}", brief.id, exc
                    )
                # GitHub public-brief sync (no-op when disabled or sub-threshold).
                try:
                    from app.notify.github_sync import push_brief
                    push_brief(db, brief)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "github_sync failed for brief={}: {}", brief.id, exc
                    )
            else:
                stats.skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.exception("brief pp={} crashed: {}", pp.id, exc)

    logger.info("briefs done: {}", stats.as_dict())
    return stats
