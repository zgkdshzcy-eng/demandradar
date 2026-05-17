"""V2EX collector via official JSON API (公开免 key).

Pulls hot topics from creative/programmer/share-related nodes.
API docs: https://www.v2ex.com/api
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize, signal_strength

# Nodes most likely to contain real-need pain points.
DEFAULT_NODES = [
    "create",        # 创意
    "ideas",         # 奇思妙想
    "programmer",    # 程序员
    "share",         # 分享发现
    "qna",           # 问与答
    "saas",          # SaaS
    "mac",           # mac 软件痛点
    "android",       # 安卓痛点
    "iphone",        # iPhone 痛点
]


class V2EXCollector(BaseCollector):
    source = "v2ex"

    def __init__(self, *, limit: int = 100, nodes: list[str] | None = None) -> None:
        super().__init__(limit=limit)
        self.nodes = nodes or DEFAULT_NODES

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        emitted = 0
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "demandradar/0.1 (contact: takedown@example.com)"},
        ) as client:
            for node in self.nodes:
                if emitted >= self.limit:
                    break
                try:
                    r = await client.get(
                        "https://www.v2ex.com/api/topics/show.json",
                        params={"node_name": node},
                    )
                    r.raise_for_status()
                    topics = r.json()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("v2ex node={} failed: {}", node, exc)
                    continue

                if not isinstance(topics, list):
                    continue

                for t in topics:
                    if emitted >= self.limit:
                        break
                    payload = self._topic_to_payload(t, node)
                    if payload is None:
                        continue
                    # Optional: only keep topics with strong/medium need signal
                    if signal_strength(payload.text, "zh") == "weak":
                        # Still emit but at low priority - useful for cluster context
                        pass
                    emitted += 1
                    yield payload

    @staticmethod
    def _topic_to_payload(t: dict, node: str) -> RawSignalPayload | None:
        tid = t.get("id")
        if tid is None:
            return None
        title = (t.get("title") or "").strip() or None
        body = "\n".join(filter(None, [t.get("title"), t.get("content")]))
        text = normalize(body)
        if not text or is_blocked(text):
            return None

        author = ((t.get("member") or {}).get("username"))
        ts = t.get("created")
        posted_at = (
            datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, (int, float)) else None
        )
        return RawSignalPayload(
            source="v2ex",
            source_item_id=str(tid),
            text=text,
            title=title,
            url=t.get("url"),
            author=author,
            lang="zh",
            score=int(t.get("replies") or 0),
            comments_count=int(t.get("replies") or 0),
            posted_at=posted_at,
            extra={"node": node},
        )
