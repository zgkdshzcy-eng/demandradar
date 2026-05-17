"""Dedupe pipeline tests using SQLite in-memory."""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.raw_signal import RawSignal
from app.pipeline.dedupe import fingerprint, run_dedupe


def test_fingerprint_normalizes_punct_and_case() -> None:
    a = fingerprint("Show HN: A tiny CSV deduper!", "body...")
    b = fingerprint("show hn a tiny csv deduper", "different body")
    assert a == b


def test_fingerprint_uses_text_when_no_title() -> None:
    a = fingerprint(None, "I really wish there was a tool to batch resize photos")
    b = fingerprint("", "i really wish there was a tool to batch resize photos!!!")
    assert a == b


def _mk(title: str, source: str, sid: str) -> RawSignal:
    return RawSignal(
        source=source,
        source_item_id=sid,
        title=title,
        text=title + " body",
        lang="en",
        collected_at=datetime.now(timezone.utc),
        processed=False,
    )


def test_run_dedupe_marks_cross_source_dups() -> None:
    with SessionLocal() as db:
        db.add_all(
            [
                _mk("Show HN: tiny CSV deduper", "hn", "h1"),
                _mk("show hn tiny csv deduper", "reddit", "r1"),  # dup
                _mk("Completely unrelated topic", "hn", "h2"),
                _mk("Another distinct post", "v2ex", "v1"),
            ]
        )
        db.commit()

        stats = run_dedupe(db, limit=100)
        assert stats.scanned == 4
        assert stats.duplicates_marked == 1
        assert stats.groups == 1

        # Re-running should be a no-op (duplicates already marked processed=True).
        stats2 = run_dedupe(db, limit=100)
        assert stats2.duplicates_marked == 0
