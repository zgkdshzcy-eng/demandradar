"""GitHub Trending collector via lightweight HTML scrape.

GitHub doesn't offer an official trending API. We pull the public HTML page
(no auth, low frequency) and parse repo cards with regex - no heavy deps.

Spec: respect robots-friendly intervals (>=24h per language) and User-Agent.
"""
from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from html import unescape

import httpx

from app.collectors.base import BaseCollector, RawSignalPayload
from app.core.logging import logger
from app.pipeline.clean import is_blocked, normalize

DEFAULT_RANGES = ["daily"]  # daily | weekly | monthly
DEFAULT_LANGS: list[str | None] = [None, "python", "typescript", "go", "rust"]

# Cards look like:
# <h2 class="h3 lh-condensed"><a ... href="/owner/repo">owner / repo</a></h2>
_REPO_RE = re.compile(
    r'<h2[^>]*class="[^"]*h3 lh-condensed[^"]*"[^>]*>\s*<a[^>]+href="(/[^"]+)"',
    re.DOTALL,
)
# Description lives in the next <p class="col-9 color-fg-muted my-1 pr-4">.
_DESC_RE = re.compile(
    r'<p[^>]*class="[^"]*col-9 color-fg-muted my-1 pr-4[^"]*"[^>]*>(.*?)</p>',
    re.DOTALL,
)
# Stars count
_STARS_RE = re.compile(
    r'<a[^>]+href="[^"]+/stargazers"[^>]*>\s*([\d,]+)\s*</a>', re.DOTALL
)


class GitHubTrendingCollector(BaseCollector):
    source = "github_trending"

    def __init__(
        self,
        *,
        limit: int = 75,
        ranges: list[str] | None = None,
        languages: list[str | None] | None = None,
    ) -> None:
        super().__init__(limit=limit)
        self.ranges = ranges or DEFAULT_RANGES
        self.languages = languages or DEFAULT_LANGS

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        emitted = 0
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "demandradar/0.1 (+takedown@example.com)",
                "Accept": "text/html",
            },
            follow_redirects=True,
        ) as client:
            for since in self.ranges:
                for lang in self.languages:
                    if emitted >= self.limit:
                        return
                    url = "https://github.com/trending"
                    if lang:
                        url += f"/{lang}"
                    try:
                        r = await client.get(url, params={"since": since})
                        r.raise_for_status()
                        html = r.text
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("github trending fetch failed: {} {}", url, exc)
                        continue

                    cards = self._parse(html)
                    for repo in cards:
                        if emitted >= self.limit:
                            return
                        payload = self._card_to_payload(repo, since=since, lang=lang)
                        if payload is None:
                            continue
                        emitted += 1
                        yield payload

    @staticmethod
    def _parse(html: str) -> list[dict]:
        # Split by <article> markers because each repo card is one article.
        articles = re.split(r'<article\b', html)[1:]
        out: list[dict] = []
        for art in articles:
            m_repo = _REPO_RE.search(art)
            if not m_repo:
                continue
            href = m_repo.group(1).strip()
            full_name = href.lstrip("/")
            m_desc = _DESC_RE.search(art)
            desc = unescape(re.sub(r"<[^>]+>", "", m_desc.group(1))).strip() if m_desc else ""
            m_stars = _STARS_RE.search(art)
            stars = int(m_stars.group(1).replace(",", "")) if m_stars else 0
            out.append({"name": full_name, "desc": desc, "stars": stars})
        return out

    @staticmethod
    def _card_to_payload(repo: dict, *, since: str, lang: str | None) -> RawSignalPayload | None:
        name = repo.get("name")
        if not name:
            return None
        body = f"{name}\n{repo.get('desc') or ''}".strip()
        text = normalize(body)
        if not text or is_blocked(text):
            return None
        return RawSignalPayload(
            source="github_trending",
            source_item_id=f"{since}:{lang or 'all'}:{name}",
            text=text,
            title=name,
            url=f"https://github.com/{name}",
            author=name.split("/")[0] if "/" in name else None,
            lang="en",
            score=int(repo.get("stars") or 0),
            comments_count=0,
            posted_at=datetime.now(timezone.utc),
            extra={"since": since, "language": lang or "all"},
        )
