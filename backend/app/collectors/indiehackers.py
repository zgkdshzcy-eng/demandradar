"""IndieHackers collector via the public group RSS feeds.

IH exposes one RSS feed per group at /group/<slug>/recent.rss. We pull a
curated set rich in "what should I build" / "looking for tool" intent.
Parsing is keyless and no-API-token.
"""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize

USER_AGENT = "demandradar/0.1 (+https://demandradar.example.com)"
INDIE_FEEDS = [
    "https://www.indiehackers.com/group/ideas-and-validation.rss",
    "https://www.indiehackers.com/group/looking-for-co-founder-or-team.rss",
    "https://www.indiehackers.com/group/feedback-please.rss",
    "https://www.indiehackers.com/group/main.rss",
]
_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _HTML_TAG.sub(" ", s)


def _parse_pubdate(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _slug_from_link(link: str) -> str:
    """e.g. https://www.indiehackers.com/post/abc123 -> abc123"""
    return link.rstrip("/").rsplit("/", 1)[-1]


class IndieHackersCollector(BaseCollector):
    source = "indiehackers"

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        emitted = 0
        seen: set[str] = set()
        async with httpx.AsyncClient(
            timeout=25.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            for feed_url in INDIE_FEEDS:
                if emitted >= self.limit:
                    break
                try:
                    r = await client.get(feed_url)
                    r.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ih feed failed url={} err={}", feed_url, exc)
                    continue

                try:
                    root = ET.fromstring(r.text)
                except ET.ParseError as exc:
                    logger.warning("ih xml parse failed url={} err={}", feed_url, exc)
                    continue

                for item in root.iter("item"):
                    if emitted >= self.limit:
                        break
                    payload = self._item_to_payload(item)
                    if payload is None:
                        continue
                    if payload.source_item_id in seen:
                        continue
                    seen.add(payload.source_item_id)
                    emitted += 1
                    yield payload

    @staticmethod
    def _item_to_payload(item: ET.Element) -> RawSignalPayload | None:
        link_el = item.find("link")
        title_el = item.find("title")
        desc_el = item.find("description")
        date_el = item.find("pubDate")
        author_el = item.find("{http://purl.org/dc/elements/1.1/}creator")

        link = (link_el.text or "").strip() if link_el is not None else ""
        title = (title_el.text or "").strip() if title_el is not None else ""
        desc = (desc_el.text or "") if desc_el is not None else ""

        if not link:
            return None
        sid = _slug_from_link(link)
        if not sid:
            return None
        text = normalize(_strip_html(desc) or title)
        if not text or is_blocked(text):
            return None

        return RawSignalPayload(
            source="indiehackers",
            source_item_id=sid,
            text=text,
            title=title or None,
            url=link,
            author=(author_el.text or "").strip() if author_el is not None else None,
            lang="en",
            score=0,
            comments_count=0,
            posted_at=_parse_pubdate(date_el.text if date_el is not None else None),
            extra={},
        )
