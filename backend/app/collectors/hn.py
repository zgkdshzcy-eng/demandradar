"""Hacker News collector via the Algolia HN Search API (public, keyless).

Docs: https://hn.algolia.com/api
We pull "Show HN" + "Ask HN" + tag:story matching seed keywords from the
last 7 days, and recent comments mentioning need-signals.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"

# Tags that already filter for high-intent posts.
_HN_QUERIES: list[dict[str, str]] = [
    {"tags": "show_hn", "query": ""},
    {"tags": "ask_hn", "query": ""},
    # Need-signal queries across all stories in past week
    {"tags": "story", "query": "is there a tool"},
    {"tags": "story", "query": "looking for"},
    {"tags": "story", "query": "alternative to"},
    {"tags": "story", "query": "wish there was"},
    {"tags": "story", "query": "would pay for"},
]


class HNCollector(BaseCollector):
    source = "hn"

    def __init__(self, *, limit: int = 100, hits_per_query: int = 30) -> None:
        super().__init__(limit=limit)
        self.hits_per_query = hits_per_query

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        emitted = 0
        async with httpx.AsyncClient(timeout=20.0) as client:
            for q in _HN_QUERIES:
                if emitted >= self.limit:
                    break
                try:
                    r = await client.get(
                        f"{ALGOLIA_BASE}/search_by_date",
                        params={
                            "tags": q["tags"],
                            "query": q["query"],
                            "hitsPerPage": self.hits_per_query,
                        },
                    )
                    r.raise_for_status()
                    data = r.json()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("HN query failed q={} err={}", q, exc)
                    continue

                for hit in data.get("hits", []):
                    if emitted >= self.limit:
                        break
                    item = self._hit_to_payload(hit)
                    if item is None:
                        continue
                    emitted += 1
                    yield item

    @staticmethod
    def _hit_to_payload(hit: dict) -> RawSignalPayload | None:
        oid = str(hit.get("objectID") or "")
        if not oid:
            return None

        title = (hit.get("title") or hit.get("story_title") or "").strip() or None
        body = (
            hit.get("comment_text")
            or hit.get("story_text")
            or hit.get("title")
            or ""
        )
        text = normalize(body)
        if not text or is_blocked(text):
            return None

        url = hit.get("url") or hit.get("story_url") or f"https://news.ycombinator.com/item?id={oid}"
        author = hit.get("author")
        ts = hit.get("created_at_i")
        posted_at = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

        return RawSignalPayload(
            source="hn",
            source_item_id=oid,
            text=text,
            title=title,
            url=url,
            author=author,
            lang="en",
            score=int(hit.get("points") or 0),
            comments_count=int(hit.get("num_comments") or 0),
            posted_at=posted_at,
            extra={"tags": hit.get("_tags")},
        )
