"""Lobste.rs collector via the public JSON API.

Lobste.rs publishes /hottest.json (50 stories) and /newest.json without auth.
We pull both and de-dup on `short_id`. Tags `ask`, `show`, `programming`,
`tech` carry the highest "is there a tool for X" signal.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize

LOBSTERS_URLS = [
    "https://lobste.rs/hottest.json",
    "https://lobste.rs/newest.json",
]
USER_AGENT = "demandradar/0.1 (+https://demandradar.example.com)"


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    # Lobste.rs returns "2026-05-06T22:11:00.000-07:00" — fromisoformat handles it on 3.11.
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class LobstersCollector(BaseCollector):
    source = "lobsters"

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        seen: set[str] = set()
        emitted = 0
        async with httpx.AsyncClient(
            timeout=20.0, headers={"User-Agent": USER_AGENT}
        ) as client:
            for url in LOBSTERS_URLS:
                if emitted >= self.limit:
                    break
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    data = r.json()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("lobsters fetch failed url={} err={}", url, exc)
                    continue

                if not isinstance(data, list):
                    continue

                for it in data:
                    if emitted >= self.limit:
                        break
                    payload = self._row_to_payload(it)
                    if payload is None:
                        continue
                    if payload.source_item_id in seen:
                        continue
                    seen.add(payload.source_item_id)
                    emitted += 1
                    yield payload

    @staticmethod
    def _row_to_payload(it: dict) -> RawSignalPayload | None:
        sid = str(it.get("short_id") or "")
        if not sid:
            return None
        title = (it.get("title") or "").strip()
        body = (
            (it.get("description") or "")
            or (it.get("comments") or "")
            or title
        )
        text = normalize(body or title)
        if not text or is_blocked(text):
            return None

        url = it.get("url") or it.get("comments_url") or it.get("short_id_url")
        author = (it.get("submitter_user") or {}).get("username")
        if isinstance(author, dict):  # older shape
            author = author.get("username")
        return RawSignalPayload(
            source="lobsters",
            source_item_id=sid,
            text=text,
            title=title or None,
            url=url,
            author=author if isinstance(author, str) else None,
            lang="en",
            score=int(it.get("score") or 0),
            comments_count=int(it.get("comment_count") or 0),
            posted_at=_parse_iso(it.get("created_at")),
            extra={"tags": it.get("tags")},
        )
