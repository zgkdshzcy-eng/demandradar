"""Cross-source near-duplicate detection.

Strategy (cheap, no extra deps):
1. Build a normalized fingerprint = lowercase + strip-punct + collapse-spaces
   over the title (or first 120 chars if no title).
2. SHA1 hash the fingerprint.
3. Group by hash; keep the earliest-collected record as canonical, mark
   the rest as `processed=true` with `extra.duplicate_of=<canonical_id>`.

This catches cross-posts (same title on Reddit + HN) and obvious copy-paste
spam. Semantic near-dup detection lives in the analyzer (cosine over embeddings).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.raw_signal import RawSignal

_PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def fingerprint(title: str | None, text: str) -> str:
    base = (title or "").strip() or text[:120]
    base = base.lower()
    base = _PUNCT_RE.sub(" ", base)
    base = " ".join(base.split())
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


@dataclass
class DedupeStats:
    scanned: int = 0
    duplicates_marked: int = 0
    groups: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "scanned": self.scanned,
            "duplicates_marked": self.duplicates_marked,
            "groups": self.groups,
        }


def run_dedupe(db: Session, *, limit: int = 5000) -> DedupeStats:
    """Scan recent unprocessed signals and mark cross-source duplicates."""
    rows: list[RawSignal] = list(
        db.execute(
            select(RawSignal)
            .where(RawSignal.processed == False)  # noqa: E712
            .order_by(RawSignal.collected_at.asc())
            .limit(limit)
        ).scalars()
    )
    stats = DedupeStats(scanned=len(rows))
    if not rows:
        return stats

    seen: dict[str, int] = {}  # fingerprint -> canonical RawSignal.id
    groups_with_dup: set[str] = set()

    for sig in rows:
        fp = fingerprint(sig.title, sig.text)
        if fp not in seen:
            seen[fp] = sig.id
            continue
        canonical_id = seen[fp]
        groups_with_dup.add(fp)
        # Mark this row as duplicate; flag processed so analyzer skips it.
        extra = dict(sig.extra or {})
        extra["duplicate_of"] = canonical_id
        sig.extra = extra
        sig.processed = True
        stats.duplicates_marked += 1

    if stats.duplicates_marked:
        db.commit()
    stats.groups = len(groups_with_dup)
    logger.info(
        "dedupe scanned={} dup_marked={} groups={}",
        stats.scanned, stats.duplicates_marked, stats.groups,
    )
    return stats
