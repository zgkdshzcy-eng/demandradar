"""Collector tests with mocked HTTP. No network required."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator

import httpx
import pytest

from app.collectors.base import BaseCollector, RawSignalPayload
from app.collectors.hn import HNCollector


# ---------- BaseCollector upsert ----------
class _DummyCollector(BaseCollector):
    source = "dummy"

    def __init__(self, items: list[RawSignalPayload]) -> None:
        super().__init__(limit=len(items))
        self._items = items

    async def fetch(self) -> AsyncIterator[RawSignalPayload]:
        for it in self._items:
            yield it


@pytest.mark.asyncio
async def test_base_collector_upsert_dedupes() -> None:
    item = RawSignalPayload(
        source="dummy",
        source_item_id="abc-1",
        text="needs better tooling",
        title="t",
        url="https://e.com",
        lang="en",
    )
    c1 = _DummyCollector([item])
    s1 = await c1.run()
    assert s1.inserted == 1 and s1.skipped == 0

    # Same id => skipped on second run
    c2 = _DummyCollector([item])
    s2 = await c2.run()
    assert s2.inserted == 0 and s2.skipped == 1


# ---------- HN collector with mocked Algolia ----------
def _fake_algolia_response() -> dict:
    return {
        "hits": [
            {
                "objectID": "100001",
                "title": "Show HN: tiny tool to dedupe csv",
                "url": "https://example.com/x",
                "author": "alice",
                "points": 42,
                "num_comments": 7,
                "created_at_i": 1_700_000_000,
                "_tags": ["show_hn", "story"],
            },
            {
                "objectID": "100002",
                "comment_text": "I wish there was a way to batch resize",
                "story_title": "Ask HN: photo workflow tools?",
                "author": "bob",
                "points": 5,
                "num_comments": 0,
                "created_at_i": 1_700_000_500,
                "_tags": ["comment"],
            },
        ]
    }


@pytest.mark.asyncio
async def test_hn_collector_with_mock(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fake_algolia_response())

    transport = httpx.MockTransport(_handler)

    # Patch httpx.AsyncClient to use our transport
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *a, **kw):  # type: ignore[no-untyped-def]
        kw["transport"] = transport
        return real_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    stats = await HNCollector(limit=5, hits_per_query=2).run()
    # 2 unique items per query, 7 queries => up to 5 (limit).
    # On second pass through same response, dedupe kicks in.
    assert stats.fetched >= 1
    assert stats.inserted >= 1
    assert stats.errors == 0


def test_payload_dataclass_defaults() -> None:
    p = RawSignalPayload(source="x", source_item_id="1", text="hi")
    assert p.lang == "unknown"
    assert p.score == 0
    assert p.extra == {}


# ---------- V2EX collector (mocked) ----------
@pytest.mark.asyncio
async def test_v2ex_collector_with_mock(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.collectors.v2ex import V2EXCollector

    fake_topics = [
        {
            "id": 901,
            "title": "求推荐：批量去水印的小工具",
            "content": "试了好几个都不行",
            "url": "https://www.v2ex.com/t/901",
            "created": 1_700_000_000,
            "replies": 5,
            "member": {"username": "alice"},
        },
        {
            "id": 902,
            "title": "有没有跨平台同步剪贴板的方案",
            "content": "Mac+Win 来回切换太麻烦",
            "url": "https://www.v2ex.com/t/902",
            "created": 1_700_000_500,
            "replies": 12,
            "member": {"username": "bob"},
        },
    ]

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fake_topics)

    transport = httpx.MockTransport(_handler)
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *a, **kw):  # type: ignore[no-untyped-def]
        kw["transport"] = transport
        return real_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    stats = await V2EXCollector(limit=10, nodes=["create", "ideas"]).run()
    # Two unique ids (901, 902); even if served twice, dedupe applies.
    assert stats.inserted >= 2
    assert stats.errors == 0


# ---------- GitHub trending parser ----------
def test_github_trending_html_parser() -> None:
    from app.collectors.trending import GitHubTrendingCollector

    html = """
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/foo/bar">foo / bar</a>
      </h2>
      <p class="col-9 color-fg-muted my-1 pr-4">A neat little tool</p>
      <a href="/foo/bar/stargazers">1,234</a>
    </article>
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/baz/qux">baz / qux</a>
      </h2>
      <p class="col-9 color-fg-muted my-1 pr-4">Another &amp; tool</p>
      <a href="/baz/qux/stargazers">42</a>
    </article>
    """
    cards = GitHubTrendingCollector._parse(html)
    assert len(cards) == 2
    assert cards[0]["name"] == "foo/bar"
    assert cards[0]["stars"] == 1234
    assert "neat" in cards[0]["desc"]
    assert cards[1]["name"] == "baz/qux"
    assert "&" in cards[1]["desc"]  # html-unescaped
