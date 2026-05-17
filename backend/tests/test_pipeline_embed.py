"""Embed pipeline test - mocks the embedder, no network/key required."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.session import SessionLocal
from app.models.raw_signal import RawSignal
from app.pipeline import embed as pipeline_embed
from app.pipeline.embed import run_embed_batch


class _FakeEmbedder:
    enabled = True

    async def embed_batch(self, texts):  # type: ignore[no-untyped-def]
        # Return deterministic non-zero vectors of length 1024.
        return [[float((hash(t) % 100) / 100.0)] * 1024 for t in texts]


@pytest.mark.asyncio
async def test_run_embed_batch_fills_vectors(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(pipeline_embed, "embedder", _FakeEmbedder())

    with SessionLocal() as db:
        for i in range(5):
            db.add(
                RawSignal(
                    source="hn",
                    source_item_id=f"e{i}",
                    text=f"sample text {i}",
                    title=f"t{i}",
                    lang="en",
                    collected_at=datetime.now(timezone.utc),
                    processed=False,
                )
            )
        db.commit()

        stats = await run_embed_batch(db, batch_size=2, max_batches=10)
        assert stats.scanned == 5
        assert stats.embedded == 5
        assert stats.errors == 0


@pytest.mark.asyncio
async def test_run_embed_batch_skips_when_disabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Disabled:
        enabled = False

        async def embed_batch(self, texts):  # type: ignore[no-untyped-def]
            raise AssertionError("should not be called")

    monkeypatch.setattr(pipeline_embed, "embedder", _Disabled())

    with SessionLocal() as db:
        stats = await run_embed_batch(db)
    assert stats.scanned == 0
    assert stats.embedded == 0
