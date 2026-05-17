"""Google Trends rising-queries collector via pytrends.

Pulls related-queries that are rising in interest for a small set of seed
topics. These are not pain-points themselves, but they signal emerging needs
and feed the analyzer's context.

pytrends is unofficial and rate-limited. We run sparingly (default daily).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.logging import logger

DEFAULT_SEEDS = [
    "ai tool",
    "automate",
    "saas",
    "no code",
    "scraper",
    "integration",
    "newsletter",
]


class GoogleTrendsCollector(BaseCollector):
    source = "google_trends"

    def __init__(
        self,
        *,
        limit: int = 60,
        seeds: list[str] | None = None,
        geo: str = "",
        timeframe: str = "now 7-d",
    ) -> None:
        super().__init__(limit=limit)
        self.seeds = seeds or DEFAULT_SEEDS
        self.geo = geo
        self.timeframe = timeframe

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        try:
            rows = await asyncio.to_thread(self._fetch_sync)
        except Exception as exc:  # noqa: BLE001
            logger.warning("google trends failed: {}", exc)
            return
        for row in rows:
            yield row

    def _fetch_sync(self) -> list[RawSignalPayload]:
        try:
            from pytrends.request import TrendReq  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("pytrends not installed; skipping")
            return []

        out: list[RawSignalPayload] = []
        try:
            pytrends = TrendReq(hl="en-US", tz=0, retries=2, backoff_factor=0.3, timeout=(10, 25))
        except Exception as exc:  # noqa: BLE001
            logger.warning("pytrends init failed: {}", exc)
            return []

        for seed in self.seeds:
            if len(out) >= self.limit:
                break
            try:
                pytrends.build_payload([seed], timeframe=self.timeframe, geo=self.geo)
                related = pytrends.related_queries() or {}
                rising = (related.get(seed) or {}).get("rising")
                if rising is None or rising.empty:
                    continue
                for _, row in rising.iterrows():
                    if len(out) >= self.limit:
                        break
                    query = str(row.get("query") or "").strip()
                    value = int(row.get("value") or 0)
                    if not query:
                        continue
                    text = f"rising query (seed='{seed}'): {query}"
                    out.append(
                        RawSignalPayload(
                            source="google_trends",
                            source_item_id=f"{seed}:{query}",
                            text=text,
                            title=query,
                            url=f"https://trends.google.com/trends/explore?q={query}",
                            lang="en",
                            score=value,
                            comments_count=0,
                            posted_at=datetime.now(timezone.utc),
                            extra={"seed": seed, "timeframe": self.timeframe, "geo": self.geo},
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("trends seed={} skipped: {}", seed, exc)
                continue
        return out
