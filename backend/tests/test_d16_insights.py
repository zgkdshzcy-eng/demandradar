"""D16 Insights tests: 3 new collectors (mocked HTTP), trend math, /api/insights."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analyze import trends as ta
from app.collectors.indiehackers import IndieHackersCollector
from app.collectors.lobsters import LobstersCollector
from app.collectors.weibo import WeiboHotCollector
from app.db import session as db_session
from app.db.session import Base
from app.models.cluster import Cluster
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal


# Per-test cleanup so each scenario builds against a known-empty DB.
@pytest.fixture(autouse=True)
def _clean_per_test():
    yield
    with db_session.engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())


# ---------------------------------------------------------------------------
# 1. Lobste.rs collector — mocked JSON
# ---------------------------------------------------------------------------

LOBSTERS_HOTTEST = [
    {
        "short_id": "abc123",
        "title": "Show: a tiny CSV deduper",
        "description": "I built this because I couldn't find a fast tool",
        "url": "https://example.com/dedup",
        "score": 42,
        "comment_count": 7,
        "created_at": "2026-04-30T22:11:00.000-07:00",
        "submitter_user": {"username": "alice"},
        "tags": ["show", "programming"],
    },
    {
        # blocked / empty — should be skipped silently.
        "short_id": "",
        "title": "no id",
    },
]


class TestLobstersCollector:
    def _client(self) -> httpx.AsyncClient:
        def handler(req: httpx.Request) -> httpx.Response:
            if "hottest" in req.url.path:
                return httpx.Response(200, json=LOBSTERS_HOTTEST)
            return httpx.Response(200, json=[])

        return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5)

    @pytest.mark.asyncio
    async def test_emits_only_well_formed_rows(self, monkeypatch) -> None:
        client = self._client()

        class _CM:
            async def __aenter__(self):
                return client

            async def __aexit__(self, *a):
                await client.aclose()

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: _CM())

        out = []
        async for p in LobstersCollector(limit=10).fetch():
            out.append(p)
        assert len(out) == 1
        item = out[0]
        assert item.source == "lobsters"
        assert item.source_item_id == "abc123"
        assert item.author == "alice"
        assert item.score == 42
        assert item.posted_at is not None and item.posted_at.tzinfo is not None
        assert "fast tool" in item.text.lower()


# ---------------------------------------------------------------------------
# 2. IndieHackers collector — mocked RSS XML
# ---------------------------------------------------------------------------

IH_RSS = """<?xml version="1.0"?><rss version="2.0"
xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>IH</title>
<item>
<title>I'm looking for a billing tool that handles refunds</title>
<link>https://www.indiehackers.com/post/foo123</link>
<description>&lt;p&gt;Hi everyone, refund flow is killing me&lt;/p&gt;</description>
<pubDate>Wed, 30 Apr 2026 12:00:00 +0000</pubDate>
<dc:creator>jane</dc:creator>
</item>
<item>
<title>Should I build X?</title>
<link>https://www.indiehackers.com/post/bar456</link>
<description>Validation question</description>
<pubDate>Tue, 29 Apr 2026 12:00:00 +0000</pubDate>
</item>
</channel></rss>"""


class TestIndieHackersCollector:
    @pytest.mark.asyncio
    async def test_parses_rss_into_signals(self, monkeypatch) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=IH_RSS)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5)

        class _CM:
            async def __aenter__(self):
                return client

            async def __aexit__(self, *a):
                await client.aclose()

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: _CM())

        out = []
        async for p in IndieHackersCollector(limit=10).fetch():
            out.append(p)
        # Same XML is returned for every feed URL but de-dup keeps it to 2.
        assert len(out) == 2
        sids = {x.source_item_id for x in out}
        assert sids == {"foo123", "bar456"}
        assert out[0].source == "indiehackers"
        assert out[0].posted_at is not None
        assert "<p>" not in out[0].text  # html stripped


# ---------------------------------------------------------------------------
# 3. Weibo hot search collector
# ---------------------------------------------------------------------------

WEIBO_PAYLOAD = {
    "ok": 1,
    "data": {
        "realtime": [
            {
                "word": "AI 替程序员写代码",
                "note": "热议中",
                "rank": 1,
                "num": 982341,
                "category": "tech",
                "label_name": "热",
                "mid": "A1",
            },
            {
                # missing word — should be skipped
                "note": "no word",
            },
        ],
        "hotgov": [],
    },
}


class TestWeiboCollector:
    @pytest.mark.asyncio
    async def test_returns_realtime_rows(self, monkeypatch) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=WEIBO_PAYLOAD)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5)

        class _CM:
            async def __aenter__(self):
                return client

            async def __aexit__(self, *a):
                await client.aclose()

        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: _CM())

        out = []
        async for p in WeiboHotCollector(limit=5).fetch():
            out.append(p)
        assert len(out) == 1
        assert out[0].lang == "zh"
        assert out[0].score == 982341
        assert "AI" in out[0].title


# ---------------------------------------------------------------------------
# 4. Trend analytics
# ---------------------------------------------------------------------------

def _seed_clustered_signals(
    db,
    *,
    pain: str,
    counts_per_week_back: list[int],
    target_user: str | None = "indie devs",
    score: float = 80.0,
) -> int:
    """Create one Cluster + PainPoint and N signals spread across weeks.

    `counts_per_week_back[0]` -> this week, `[1]` -> last week, etc.
    Returns painpoint id.
    """
    c = Cluster(label=pain, size=sum(counts_per_week_back))
    db.add(c)
    db.flush()
    pp = PainPoint(
        cluster_id=c.id, pain=pain, target_user=target_user, total_score=score, go_no_go="go"
    )
    db.add(pp)
    db.flush()

    monday = ta._iso_week_start(datetime.now(tz=timezone.utc))
    for offset_w, n in enumerate(counts_per_week_back):
        # Place each signal mid-week (Wednesday 12:00 UTC) of the target week.
        when = monday - timedelta(weeks=offset_w) + timedelta(days=2, hours=12)
        for i in range(n):
            db.add(
                RawSignal(
                    source="hn",
                    source_item_id=f"{pain}-{offset_w}-{i}",
                    text="x",
                    title="x",
                    lang="en",
                    cluster_id=c.id,
                    posted_at=when,
                    collected_at=when,
                )
            )
    db.commit()
    return pp.id


class TestTrendAnalytics:
    def test_iso_week_start_is_monday_utc(self) -> None:
        d = datetime(2026, 5, 7, 12, 30, tzinfo=timezone.utc)  # Thu
        m = ta._iso_week_start(d)
        assert m.weekday() == 0
        assert (m.hour, m.minute, m.second) == (0, 0, 0)
        assert m.tzinfo is not None

    def test_weekly_heat_buckets_signals_into_correct_weeks(self) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="A", counts_per_week_back=[5, 2, 0, 0, 0, 0])
            _seed_clustered_signals(db, pain="B", counts_per_week_back=[1, 1, 1, 0, 0, 0])
            heat = ta.weekly_heat(db, weeks=6)
        # Painpoint A should rank first by total (7 vs 3).
        assert [h.pain for h in heat] == ["A", "B"]
        a = heat[0]
        # 6 weeks materialised, this-week is the last bucket
        assert len(a.weeks) == 6
        assert a.weeks[-1].count == 5  # this week
        assert a.weeks[-2].count == 2  # last week

    def test_weekly_heat_skips_painpoints_with_zero_window(self) -> None:
        with db_session.SessionLocal() as db:
            # 8 weeks ago — outside default 6-week window
            _seed_clustered_signals(db, pain="OLD", counts_per_week_back=[0] * 7 + [5])
            heat = ta.weekly_heat(db, weeks=6)
        assert heat == []

    def test_top_movers_ranks_by_wow_delta(self) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="up", counts_per_week_back=[10, 2])
            _seed_clustered_signals(db, pain="flat", counts_per_week_back=[3, 3])
            _seed_clustered_signals(db, pain="down", counts_per_week_back=[2, 8])
            movers = ta.top_movers(db, lookback_weeks=2, min_signals=3)
        names = [m.pain for m in movers]
        assert names[0] == "up"
        assert names[-1] == "down"
        up = movers[0]
        assert up.delta == 8
        assert up.delta_pct == 400.0  # 2 -> 10 == +400%

    def test_top_movers_filters_out_below_min_signals(self) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="tiny", counts_per_week_back=[1, 1])
            movers = ta.top_movers(db, lookback_weeks=2, min_signals=3)
        assert movers == []

    def test_evidence_timeline_returns_sorted_desc(self) -> None:
        with db_session.SessionLocal() as db:
            pp_id = _seed_clustered_signals(db, pain="tl", counts_per_week_back=[3, 0, 0])
            tl = ta.evidence_timeline(db, pp_id, limit=10)
        assert tl
        # Newest first
        for a, b in zip(tl, tl[1:]):
            assert a.posted_at >= b.posted_at

    def test_evidence_timeline_unknown_id(self) -> None:
        with db_session.SessionLocal() as db:
            assert ta.evidence_timeline(db, 999_999) == []

    def test_source_breakdown_counts_recent_signals(self) -> None:
        with db_session.SessionLocal() as db:
            now = datetime.now(tz=timezone.utc)
            for src, n in [("hn", 3), ("v2ex", 2), ("weibo", 1)]:
                for i in range(n):
                    db.add(
                        RawSignal(
                            source=src,
                            source_item_id=f"{src}-{i}",
                            text="x",
                            title="x",
                            collected_at=now,
                        )
                    )
            db.commit()
            breakdown = ta.source_breakdown(db, since_days=30)
        assert breakdown == {"hn": 3, "v2ex": 2, "weibo": 1}


# ---------------------------------------------------------------------------
# 5. /api/insights endpoints
# ---------------------------------------------------------------------------

class TestInsightsAPI:
    def test_heat_endpoint(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="api-heat", counts_per_week_back=[4, 1])
        r = client.get("/api/insights/heat?weeks=2&limit=5")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list) and body
        first = body[0]
        assert first["pain"] == "api-heat"
        assert first["total"] == 5
        assert len(first["weeks"]) == 2

    def test_movers_endpoint_excludes_inf_pct(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="zero-to-many", counts_per_week_back=[5, 0])
        r = client.get("/api/insights/movers?limit=5&min_signals=3")
        assert r.status_code == 200
        body = r.json()
        assert body
        # last_week == 0 -> delta_pct should be null (we don't return inf).
        assert body[0]["delta_pct"] is None

    def test_movers_min_signals_default(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="below-cut", counts_per_week_back=[1, 1])
        r = client.get("/api/insights/movers?min_signals=3")
        assert r.status_code == 200
        assert r.json() == []

    def test_timeline_endpoint(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            pp_id = _seed_clustered_signals(db, pain="tl-api", counts_per_week_back=[2, 0])
        r = client.get(f"/api/insights/timeline/{pp_id}")
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 2
        assert "posted_at" in rows[0]

    def test_sources_endpoint(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            now = datetime.now(tz=timezone.utc)
            for src in ("hn", "weibo"):
                db.add(RawSignal(source=src, source_item_id=src, text="x", collected_at=now))
            db.commit()
        r = client.get("/api/insights/sources?days=30")
        assert r.status_code == 200
        body = r.json()
        assert body.get("hn") == 1 and body.get("weibo") == 1

    def test_csv_export_heat(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="csv-heat", counts_per_week_back=[2, 1])
        r = client.get("/api/insights/export.csv?kind=heat&weeks=2")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert r.headers["content-disposition"].endswith('"painpoint_heat.csv"')
        body = r.text
        assert "pain_point_id" in body and "csv-heat" in body

    def test_csv_export_movers(self, client: TestClient) -> None:
        with db_session.SessionLocal() as db:
            _seed_clustered_signals(db, pain="csv-mov", counts_per_week_back=[5, 1])
        r = client.get("/api/insights/export.csv?kind=movers")
        assert r.status_code == 200
        assert "csv-mov" in r.text

    def test_csv_export_timeline_requires_id(self, client: TestClient) -> None:
        r = client.get("/api/insights/export.csv?kind=timeline")
        assert r.status_code == 400

    def test_csv_export_unknown_kind(self, client: TestClient) -> None:
        r = client.get("/api/insights/export.csv?kind=bogus")
        # FastAPI's Literal validation kicks in first -> 422.
        assert r.status_code in (400, 422)
