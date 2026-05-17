"""Reddit collector via PRAW (read-only app, official API).

Requires REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET. Disabled gracefully when
credentials are missing.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.config import settings
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize

# Subreddits with high signal-to-noise for indie dev needs.
DEFAULT_SUBREDDITS = [
    "SaaS",
    "Entrepreneur",
    "sideproject",
    "indiehackers",
    "smallbusiness",
    "selfhosted",
    "productivity",
    "ecommerce",
    "freelance",
    "webdev",
]


class RedditCollector(BaseCollector):
    source = "reddit"

    def __init__(
        self,
        *,
        limit: int = 100,
        subreddits: list[str] | None = None,
        per_sub: int = 25,
        listing: str = "new",  # new | hot | top
    ) -> None:
        super().__init__(limit=limit)
        self.subreddits = subreddits or DEFAULT_SUBREDDITS
        self.per_sub = per_sub
        self.listing = listing

    def _enabled(self) -> bool:
        return bool(settings.reddit_client_id and settings.reddit_client_secret)

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        if not self._enabled():
            logger.info("reddit collector skipped: credentials not set")
            return

        items = await asyncio.to_thread(self._fetch_sync)
        for it in items:
            yield it

    def _fetch_sync(self) -> list[RawSignalPayload]:
        import praw  # local import to avoid hard dependency at startup

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            check_for_async=False,
        )
        reddit.read_only = True

        out: list[RawSignalPayload] = []
        for sub in self.subreddits:
            if len(out) >= self.limit:
                break
            try:
                sr = reddit.subreddit(sub)
                listing = getattr(sr, self.listing)(limit=self.per_sub)
                for post in listing:
                    if len(out) >= self.limit:
                        break
                    payload = self._post_to_payload(post, sub)
                    if payload is not None:
                        out.append(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("reddit sub={} failed: {}", sub, exc)
                continue
        return out

    @staticmethod
    def _post_to_payload(post, subreddit: str) -> RawSignalPayload | None:  # type: ignore[no-untyped-def]
        body = (post.title or "") + "\n\n" + (post.selftext or "")
        text = normalize(body)
        if not text or is_blocked(text):
            return None
        return RawSignalPayload(
            source="reddit",
            source_item_id=str(post.id),
            text=text,
            title=post.title,
            url=f"https://www.reddit.com{post.permalink}",
            author=str(post.author) if post.author else None,
            lang="en",
            score=int(post.score or 0),
            comments_count=int(post.num_comments or 0),
            posted_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
            extra={"subreddit": subreddit, "flair": post.link_flair_text},
        )
