"""API tests for /api/painpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.cluster import Cluster
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal


def _seed(db) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    cluster = Cluster(label="csv tools", size=2, lang_primary="en")
    db.add(cluster)
    db.flush()

    sig = RawSignal(
        source="hn",
        source_item_id="api-1",
        text="i wish there was a csv batch tool",
        title="CSV pain",
        lang="en",
        collected_at=datetime.now(timezone.utc),
        cluster_id=cluster.id,
        processed=True,
    )
    db.add(sig)
    db.flush()

    pp_high = PainPoint(
        cluster_id=cluster.id,
        pain="批量处理 CSV 太慢",
        frequency_signal="high",
        emotion="anxiety",
        willingness_to_pay_signal="strong",
        evidence_quote="i wish there was a tool",
        source_signal_ids=[sig.id],
        pain_intensity=5,
        frequency=5,
        willingness_to_pay=5,
        reach_difficulty=4,
        dev_difficulty=4,
        competition=3,
        differentiation=4,
        automation_potential=5,
        virality=3,
        retention=3,
        total_score=85.0,
        go_no_go="go",
        rationale="strong fit",
    )
    pp_low = PainPoint(
        cluster_id=cluster.id,
        pain="冷门小问题",
        frequency_signal="low",
        emotion="neutral",
        willingness_to_pay_signal="weak",
        source_signal_ids=[sig.id],
        total_score=25.0,
        go_no_go="drop",
    )
    db.add_all([pp_high, pp_low])
    db.commit()
    return pp_high.id, pp_low.id


def test_top_returns_only_go(client: TestClient) -> None:
    with SessionLocal() as db:
        high_id, low_id = _seed(db)

    r = client.get("/api/painpoints/top", params={"limit": 10})
    assert r.status_code == 200
    items = r.json()
    ids = [i["id"] for i in items]
    assert high_id in ids
    assert low_id not in ids
    top = next(i for i in items if i["id"] == high_id)
    assert top["go_no_go"] == "go"
    assert top["scores"]["pain_intensity"] == 5
    assert top["evidence"][0]["source"] == "hn"


def test_list_filters_by_min_score(client: TestClient) -> None:
    r = client.get("/api/painpoints", params={"min_score": 80, "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    for it in body["items"]:
        assert it["total_score"] >= 80


def test_get_one(client: TestClient) -> None:
    r = client.get("/api/painpoints", params={"limit": 1})
    pid = r.json()["items"][0]["id"]
    r2 = client.get(f"/api/painpoints/{pid}")
    assert r2.status_code == 200
    assert r2.json()["id"] == pid


def test_stats_endpoint(client: TestClient) -> None:
    r = client.get("/api/painpoints/-/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert body["scored"] >= 2
    assert body["avg_score"] is not None
