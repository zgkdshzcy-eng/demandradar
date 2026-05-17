"""Weibo hot search collector.

Weibo exposes a public side hot-search endpoint that returns the realtime
trending list as JSON. No login required (cookie optional). We pull the top
50, filter out pure entertainment chatter via the cleaning pipeline, and
emit one RawSignal per entry.

Source: https://weibo.com/ajax/side/hotSearch
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize

WEIBO_HOT_URL = "https://weibo.com/ajax/side/hotSearch"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Safari/605.1.15 demandradar/0.1"
)


class WeiboHotCollector(BaseCollector):
    source = "weibo"

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        emitted = 0
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://weibo.com/hot/search",
            },
        ) as client:
            try:
                r = await client.get(WEIBO_HOT_URL)
                r.raise_for_status()
                data = r.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("weibo hot fetch failed: {}", exc)
                return

        # Endpoint shape: {"ok":1,"data":{"realtime":[{...}], "hotgov":[{...}]}}
        rows = (data.get("data") or {}).get("realtime") or []
        now = datetime.now(timezone.utc)
        for it in rows:
            if emitted >= self.limit:
                break
            payload = self._row_to_payload(it, now)
            if payload is None:
                continue
            emitted += 1
            yield payload

    @staticmethod
    def _row_to_payload(it: dict, now: datetime) -> RawSignalPayload | None:
        word = (it.get("word") or "").strip()
        if not word:
            return None
        # `note` is usually a 1-line context; `flag` = sticky/promoted index.
        note = (it.get("note") or "").strip()
        text = normalize(f"{word} {note}".strip())
        if not text or is_blocked(text):
            return None

        # Use the trending word itself as the stable id; weibo provides a
        # `mid` only for some rows. Fall back keeps idempotency.
        sid = str(it.get("mid") or word)[:96]
        rank = it.get("rank")
        url = (
            f"https://s.weibo.com/weibo?q=%23{word}%23"
        )

        return RawSignalPayload(
            source="weibo",
            source_item_id=sid,
            text=text,
            title=word,
            url=url,
            author=None,
            lang="zh",
            score=int(it.get("num") or 0),  # heat score (热度)
            comments_count=0,
            posted_at=now,
            extra={
                "rank": rank,
                "category": it.get("category"),
                "label_name": it.get("label_name"),
            },
        )
