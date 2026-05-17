"""Cluster -> PainPoint extraction via LLM JSON.

For each cluster lacking PainPoints, take the top N representative signals
(highest score, recent, distinct authors), render the pain_extract prompt,
call LLM JSON mode, persist PainPoint rows linked to cluster + source signals.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analyzer.prompts import load_prompt, render
from app.core.llm import llm
from app.core.logging import logger
from app.models.cluster import Cluster
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal

# Cap how many signals we feed per cluster (cost control + prompt budget).
MAX_SIGNALS_PER_CLUSTER = 20
MAX_TEXT_CHARS = 600


@dataclass
class ExtractStats:
    clusters_seen: int = 0
    clusters_skipped: int = 0
    clusters_processed: int = 0
    pain_points_inserted: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _pick_representatives(db: Session, cluster_id: int) -> list[RawSignal]:
    rows: list[RawSignal] = list(
        db.execute(
            select(RawSignal)
            .where(RawSignal.cluster_id == cluster_id)
            .order_by(RawSignal.score.desc(), RawSignal.collected_at.desc())
            .limit(MAX_SIGNALS_PER_CLUSTER)
        ).scalars()
    )
    return rows


def _build_input_json(signals: list[RawSignal]) -> str:
    items = []
    for s in signals:
        text = (s.title or "") + ("\n" + s.text if s.text else "")
        items.append(
            {
                "id": s.id,
                "source": s.source,
                "url": s.url,
                "lang": s.lang,
                "score": s.score,
                "text": text[:MAX_TEXT_CHARS],
            }
        )
    return json.dumps(items, ensure_ascii=False)


async def extract_one_cluster(db: Session, cluster: Cluster) -> int:
    """Run extraction for a single cluster. Returns number of PainPoints inserted."""
    signals = _pick_representatives(db, cluster.id)
    if len(signals) < 2:
        logger.debug("cluster {} has <2 reps, skip", cluster.id)
        return 0

    # D17: prefer the localised prompt that matches the dominant language of
    # the cluster's evidence so the LLM responds in the right language.
    from app.analyzer.prompts import detect_lang
    sample_text = " ".join(((s.text or s.title or "")[:200]) for s in signals[:5])
    lang = detect_lang(sample_text)
    system, user_tpl = load_prompt("pain_extract", lang=lang)
    user_prompt = render(user_tpl, INPUT_JSON=_build_input_json(signals))

    try:
        result = await llm.complete_json(
            user_prompt, system=system, temperature=0.2,
            task="extract", purpose="extract",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM extract failed cluster={}: {}", cluster.id, exc)
        return 0

    # Result may be a list, or a dict with key like "pain_points" or "items".
    items: list[dict] = []
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        for key in ("pain_points", "items", "data", "results"):
            if isinstance(result.get(key), list):
                items = result[key]
                break
        if not items and any(isinstance(v, list) for v in result.values()):
            for v in result.values():
                if isinstance(v, list):
                    items = v
                    break

    inserted = 0
    sig_id_set = {s.id for s in signals}
    for it in items:
        if not isinstance(it, dict):
            continue
        pain = (it.get("pain") or "").strip()
        if not pain:
            continue
        # Map source_ids back to actual signal ids; tolerate missing.
        raw_ids = it.get("source_ids") or []
        valid_ids = []
        for rid in raw_ids:
            try:
                rid_int = int(rid)
            except (TypeError, ValueError):
                continue
            if rid_int in sig_id_set:
                valid_ids.append(rid_int)
        if not valid_ids:
            valid_ids = [signals[0].id]  # fallback to first rep

        pp = PainPoint(
            cluster_id=cluster.id,
            pain=pain[:255],
            scenario=(it.get("scenario") or None) and str(it["scenario"])[:500],
            target_user=(it.get("target_user") or None) and str(it["target_user"])[:255],
            frequency_signal=str(it.get("frequency_signal") or "medium")[:16],
            emotion=str(it.get("emotion") or "neutral")[:16],
            willingness_to_pay_signal=str(it.get("willingness_to_pay_signal") or "weak")[:16],
            diy_workaround=it.get("diy_workaround") or None,
            evidence_quote=(it.get("evidence_quote") or None) and str(it["evidence_quote"])[:500],
            source_signal_ids=valid_ids,
        )
        db.add(pp)
        inserted += 1

    if inserted:
        # Mark source signals processed so they don't recluster.
        for s in signals:
            s.processed = True
        db.commit()
    else:
        db.rollback()
    return inserted


async def run_extract(db: Session, *, max_clusters: int = 10) -> ExtractStats:
    """Process clusters that have no PainPoint yet."""
    stats = ExtractStats()

    # Subquery: cluster_ids that already have at least one PainPoint.
    sub = select(PainPoint.cluster_id).where(PainPoint.cluster_id.is_not(None)).distinct()
    rows: list[Cluster] = list(
        db.execute(
            select(Cluster)
            .where(Cluster.id.not_in(sub))
            .order_by(Cluster.size.desc(), Cluster.id.desc())
            .limit(max_clusters)
        ).scalars()
    )
    stats.clusters_seen = len(rows)
    if not rows:
        logger.info("extract: no fresh clusters to process")
        return stats

    for cl in rows:
        try:
            n = await extract_one_cluster(db, cl)
            if n > 0:
                stats.clusters_processed += 1
                stats.pain_points_inserted += n
            else:
                stats.clusters_skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.exception("extract cluster={} crashed: {}", cl.id, exc)

    logger.info("extract done: {}", stats.as_dict())
    return stats
