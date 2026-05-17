"""BaseCollector: shared interface + idempotent upsert into raw_signals.

Every collector implements `fetch()` that yields RawSignalPayload dicts.
The base class handles dedupe via the `(source, source_item_id)` unique key.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.models.raw_signal import RawSignal


@dataclass
class RawSignalPayload:
    """Source-agnostic raw record. Collectors emit these."""

    source: str
    source_item_id: str
    text: str
    title: str | None = None
    url: str | None = None
    author: str | None = None
    lang: str = "unknown"
    score: int = 0
    comments_count: int = 0
    posted_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectStats:
    fetched: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "fetched": self.fetched,
            "inserted": self.inserted,
            "skipped": self.skipped,
            "errors": self.errors,
        }


class BaseCollector(ABC):
    """Subclass and implement :meth:`fetch`."""

    source: str = "base"

    def __init__(self, *, limit: int = 100) -> None:
        self.limit = limit

    @abstractmethod
    async def fetch(self) -> AsyncIterator[RawSignalPayload]:  # pragma: no cover
        """Yield RawSignalPayload one by one."""
        if False:  # pragma: no cover
            yield  # type: ignore[unreachable]

    async def run(self) -> CollectStats:
        """Drive `fetch()` and persist with idempotent upsert."""
        stats = CollectStats()
        try:
            async for item in self.fetch():
                stats.fetched += 1
                if await self._persist(item):
                    stats.inserted += 1
                else:
                    stats.skipped += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            logger.exception("collector {} failed: {}", self.source, exc)
        logger.info(
            "collector source={} fetched={} inserted={} skipped={} errors={}",
            self.source, stats.fetched, stats.inserted, stats.skipped, stats.errors,
        )
        return stats

    async def _persist(self, item: RawSignalPayload) -> bool:
        """Insert one signal; return True if newly inserted, False if duplicate.

        Uses Postgres ON CONFLICT DO NOTHING for atomicity. Falls back to
        SELECT-then-INSERT on non-Postgres dialects (tests on SQLite).
        """
        from app.db import session as db_mod

        with db_mod.SessionLocal() as db:
            dialect = db.bind.dialect.name if db.bind else "postgresql"
            payload = {
                "source": item.source,
                "source_item_id": item.source_item_id,
                "url": item.url,
                "author": item.author,
                "lang": item.lang,
                "title": item.title,
                "text": item.text,
                "score": item.score,
                "comments_count": item.comments_count,
                "posted_at": item.posted_at,
                "collected_at": datetime.now(timezone.utc),
                "extra": item.extra or None,
            }

            if dialect == "postgresql":
                stmt = (
                    pg_insert(RawSignal)
                    .values(**payload)
                    .on_conflict_do_nothing(index_elements=["source", "source_item_id"])
                    .returning(RawSignal.id)
                )
                res = db.execute(stmt).scalar_one_or_none()
                db.commit()
                return res is not None

            # generic fallback (sqlite/tests)
            existing = db.execute(
                select(RawSignal.id).where(
                    RawSignal.source == item.source,
                    RawSignal.source_item_id == item.source_item_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return False
            db.add(RawSignal(**payload))
            try:
                db.commit()
                return True
            except IntegrityError:
                db.rollback()
                return False
