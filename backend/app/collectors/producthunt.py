"""Product Hunt collector via the official GraphQL API v2.

Requires PRODUCT_HUNT_TOKEN (developer token from https://api.producthunt.com/v2/oauth/applications).
Skipped gracefully when token missing.

We pull recent posts (with tagline + description) and a few top comments.
The signal: existing PH posts with high comment counts often expose
adjacent unmet needs in the comments.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.config import settings
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize

PH_GRAPHQL = "https://api.producthunt.com/v2/api/graphql"

POSTS_QUERY = """
query RecentPosts($first: Int!) {
  posts(order: NEWEST, first: $first) {
    edges {
      node {
        id
        name
        tagline
        description
        url
        votesCount
        commentsCount
        createdAt
        user { name }
        topics(first: 5) { edges { node { name } } }
      }
    }
  }
}
"""


class ProductHuntCollector(BaseCollector):
    source = "producthunt"

    def __init__(self, *, limit: int = 50) -> None:
        super().__init__(limit=limit)

    def _enabled(self) -> bool:
        return bool(settings.product_hunt_token)

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        if not self._enabled():
            logger.info("producthunt collector skipped: PRODUCT_HUNT_TOKEN not set")
            return

        headers = {
            "Authorization": f"Bearer {settings.product_hunt_token}",
            "Content-Type": "application/json",
            "User-Agent": "demandradar/0.1",
        }
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            try:
                r = await client.post(
                    PH_GRAPHQL,
                    json={"query": POSTS_QUERY, "variables": {"first": min(self.limit, 50)}},
                )
                r.raise_for_status()
                data = r.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("PH query failed: {}", exc)
                return

            edges = ((data.get("data") or {}).get("posts") or {}).get("edges", [])
            for edge in edges:
                node = edge.get("node") or {}
                payload = self._node_to_payload(node)
                if payload is not None:
                    yield payload

    @staticmethod
    def _node_to_payload(node: dict) -> RawSignalPayload | None:
        nid = str(node.get("id") or "")
        if not nid:
            return None
        body = "\n".join(filter(None, [node.get("tagline"), node.get("description")]))
        text = normalize(body)
        if not text or is_blocked(text):
            return None
        topics = [
            (t.get("node") or {}).get("name")
            for t in (node.get("topics", {}) or {}).get("edges", [])
        ]
        created = node.get("createdAt")
        posted_at = None
        if created:
            try:
                posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                pass
        return RawSignalPayload(
            source="producthunt",
            source_item_id=nid,
            text=text,
            title=node.get("name"),
            url=node.get("url"),
            author=((node.get("user") or {}).get("name")),
            lang="en",
            score=int(node.get("votesCount") or 0),
            comments_count=int(node.get("commentsCount") or 0),
            posted_at=posted_at,
            extra={"topics": [t for t in topics if t]},
        )
