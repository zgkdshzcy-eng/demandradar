"""Clustering tests with synthetic embeddings."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.cluster import Cluster
from app.models.raw_signal import RawSignal
from app.pipeline.cluster import run_cluster


def _vec(seed: int, jitter: float = 0.0) -> list[float]:
    """Generate a 1024-dim unit vector controlled by seed (group) + jitter."""
    base = [0.0] * 1024
    # Distinct directions per seed.
    for i in range(0, 1024, 8):
        base[i + (seed % 8)] = 1.0
    # Add tiny noise to make members distinct but close.
    if jitter:
        for k in range(1024):
            base[k] += jitter * math.sin(k + seed * 7 + 13)
    # Normalize
    n = math.sqrt(sum(x * x for x in base)) or 1.0
    return [x / n for x in base]


def test_run_cluster_groups_similar_signals() -> None:
    with SessionLocal() as db:
        # Group A: 4 near-identical vectors (seed=1)
        for i in range(4):
            db.add(
                RawSignal(
                    source="hn",
                    source_item_id=f"a{i}",
                    text=f"group A signal {i}",
                    title=f"A {i}",
                    lang="en",
                    collected_at=datetime.now(timezone.utc),
                    processed=False,
                    embedding=_vec(1, jitter=0.001 * i),
                )
            )
        # Group B: 4 near-identical vectors (seed=2)
        for i in range(4):
            db.add(
                RawSignal(
                    source="reddit",
                    source_item_id=f"b{i}",
                    text=f"group B signal {i}",
                    title=f"B {i}",
                    lang="en",
                    collected_at=datetime.now(timezone.utc),
                    processed=False,
                    embedding=_vec(2, jitter=0.001 * i),
                )
            )
        # 1 outlier (singleton)
        db.add(
            RawSignal(
                source="v2ex",
                source_item_id="x1",
                text="outlier",
                title="X",
                lang="zh",
                collected_at=datetime.now(timezone.utc),
                processed=False,
                embedding=_vec(7),
            )
        )
        db.commit()

        stats = run_cluster(db, eps=0.30, min_samples=3)
        assert stats.candidates == 9
        assert stats.new_clusters == 2
        assert stats.clustered == 8
        assert stats.singletons == 1

        # Re-running should be idempotent (no new candidates).
        stats2 = run_cluster(db)
        assert stats2.candidates == 1  # only the outlier remains; below min_samples
        assert stats2.new_clusters == 0


def test_cluster_skips_when_few_candidates() -> None:
    with SessionLocal() as db:
        # Wipe state from previous test by inserting a single fresh row only.
        db.add(
            RawSignal(
                source="hn",
                source_item_id="solo-1",
                text="lonely",
                title="solo",
                lang="en",
                collected_at=datetime.now(timezone.utc),
                processed=False,
                embedding=_vec(3),
            )
        )
        db.commit()
        before = db.query(Cluster).count()
        stats = run_cluster(db, min_samples=3)
        # 1 candidate < min_samples -> skip
        assert stats.new_clusters == 0
        assert db.query(Cluster).count() == before
