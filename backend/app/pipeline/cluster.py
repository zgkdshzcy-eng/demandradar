"""Semantic clustering: DBSCAN over embeddings -> Cluster rows.

We use sklearn's DBSCAN with cosine distance. Compared to HDBSCAN it requires
no native build (Windows-friendly) and is good enough for our scale
(<= ~50k vectors / batch). When data grows, swap in HDBSCAN here.

Output:
- New `Cluster` rows with centroid (l2-mean of members), size, lang_primary.
- `RawSignal.cluster_id` filled for clustered rows.
- Singletons (DBSCAN label == -1) keep cluster_id = NULL; they will be
  retried in the next round when more similar signals arrive.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.cluster import Cluster
from app.models.raw_signal import RawSignal


@dataclass
class ClusterStats:
    candidates: int = 0
    clustered: int = 0
    singletons: int = 0
    new_clusters: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "candidates": self.candidates,
            "clustered": self.clustered,
            "singletons": self.singletons,
            "new_clusters": self.new_clusters,
        }


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def _label(texts: list[str]) -> str:
    """Cheap label: most common 2-3 word token in titles."""
    tokens: Counter[str] = Counter()
    for t in texts:
        # Crude: take first 6 tokens of normalized title.
        for tok in t.lower().split()[:6]:
            tok = tok.strip(".,!?;:()[]{}\"'")
            if len(tok) >= 3:
                tokens[tok] += 1
    common = [w for w, _ in tokens.most_common(3)]
    return " / ".join(common) if common else "untitled"


def run_cluster(
    db: Session,
    *,
    eps: float = 0.30,
    min_samples: int = 3,
    batch: int = 2000,
) -> ClusterStats:
    """One-shot clustering pass over unclustered, embedded, unprocessed signals."""
    rows: list[RawSignal] = list(
        db.execute(
            select(RawSignal)
            .where(RawSignal.embedding.is_not(None))
            .where(RawSignal.cluster_id.is_(None))
            .where(RawSignal.processed == False)  # noqa: E712
            .order_by(RawSignal.collected_at.desc())
            .limit(batch)
        ).scalars()
    )
    stats = ClusterStats(candidates=len(rows))
    if len(rows) < min_samples:
        logger.info("cluster: too few candidates ({}); skipping", len(rows))
        return stats

    X = np.array([list(r.embedding) for r in rows], dtype=np.float32)  # type: ignore[arg-type]
    X = _l2_normalize(X)

    dbs = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine", n_jobs=-1)
    labels = dbs.fit_predict(X)

    # Group row indices by label.
    groups: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels):
        groups.setdefault(int(lab), []).append(idx)

    for lab, idxs in groups.items():
        if lab == -1:
            stats.singletons += len(idxs)
            continue
        members = [rows[i] for i in idxs]
        member_vecs = X[idxs]
        centroid = _l2_normalize(member_vecs.mean(axis=0, keepdims=True))[0].tolist()
        titles = [(m.title or m.text[:60]) for m in members]
        lang_counts = Counter(m.lang for m in members)
        lang_primary = lang_counts.most_common(1)[0][0] if lang_counts else "unknown"

        cluster = Cluster(
            label=_label(titles)[:120],
            summary=None,
            centroid=centroid,
            size=len(members),
            lang_primary=lang_primary,
        )
        db.add(cluster)
        db.flush()  # need cluster.id before assigning to members

        for m in members:
            m.cluster_id = cluster.id
        stats.clustered += len(members)
        stats.new_clusters += 1

    db.commit()
    logger.info(
        "cluster done: candidates={} clustered={} singletons={} new_clusters={}",
        stats.candidates, stats.clustered, stats.singletons, stats.new_clusters,
    )
    return stats
