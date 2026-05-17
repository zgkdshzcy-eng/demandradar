"""Batch-embed unprocessed RawSignals and persist into pgvector.

We deliberately do NOT mark `processed=true` here - that flag is owned by the
analyzer (Day 5). This stage only fills `embedding`. A signal can be re-embedded
later if the model changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.embed import embedder
from app.core.logging import logger
from app.models.raw_signal import RawSignal


@dataclass
class EmbedStats:
    scanned: int = 0
    embedded: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "scanned": self.scanned,
            "embedded": self.embedded,
            "skipped": self.skipped,
            "errors": self.errors,
        }


# Truncate long text before embedding to control cost.
MAX_CHARS = 1500


def _prep(sig: RawSignal) -> str:
    title = (sig.title or "").strip()
    body = (sig.text or "").strip()
    text = f"{title}\n{body}".strip() if title else body
    return text[:MAX_CHARS]


async def run_embed_batch(db: Session, *, batch_size: int = 64, max_batches: int = 50) -> EmbedStats:
    """Embed up to batch_size * max_batches signals lacking embeddings."""
    stats = EmbedStats()
    if not embedder.enabled:
        logger.info("embedding skipped: EMBEDDING_API_KEY not configured")
        return stats

    for _ in range(max_batches):
        rows: list[RawSignal] = list(
            db.execute(
                select(RawSignal)
                .where(RawSignal.embedding.is_(None))
                .where(RawSignal.processed == False)  # noqa: E712
                .order_by(RawSignal.collected_at.asc())
                .limit(batch_size)
            ).scalars()
        )
        if not rows:
            break
        stats.scanned += len(rows)

        texts = [_prep(r) for r in rows]
        try:
            vectors = await embedder.embed_batch(texts)
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.exception("embed batch failed: {}", exc)
            break

        if len(vectors) != len(rows):
            stats.errors += 1
            logger.error("embed length mismatch: {} vs {}", len(vectors), len(rows))
            break

        for sig, vec in zip(rows, vectors):
            try:
                sig.embedding = vec
                stats.embedded += 1
            except Exception as exc:  # noqa: BLE001
                stats.errors += 1
                logger.warning("embed assign failed id={} err={}", sig.id, exc)

        db.commit()

    logger.info(
        "embed scanned={} embedded={} skipped={} errors={}",
        stats.scanned, stats.embedded, stats.skipped, stats.errors,
    )
    return stats
