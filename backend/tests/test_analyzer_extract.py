"""Pain extraction test with mocked LLM."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.analyzer import extract as extract_mod
from app.db.session import SessionLocal
from app.models.cluster import Cluster
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal


class _FakeLLM:
    async def complete_json(self, prompt, *, system=None, temperature=0.2, **kw):  # type: ignore[no-untyped-def]
        # Echo back two reasonable pain points referencing first signal id.
        # The function infers source_ids fallback when missing.
        return [
            {
                "pain": "无法批量处理大文件",
                "scenario": "数据分析师每天手工切分 CSV",
                "target_user": "数据分析师",
                "frequency_signal": "high",
                "emotion": "anxiety",
                "willingness_to_pay_signal": "strong",
                "diy_workaround": "用 Excel 一个个切",
                "evidence_quote": "求一个能批量切 CSV 的工具",
                "source_ids": [],  # force fallback to signals[0]
            },
            {
                "pain": "导出格式不兼容",
                "scenario": "甲方要求 PDF/A 格式",
                "target_user": "出版编辑",
                "frequency_signal": "medium",
                "emotion": "helplessness",
                "willingness_to_pay_signal": "weak",
                "evidence_quote": "导出 PDF/A 总是失败",
            },
        ]


@pytest.mark.asyncio
async def test_run_extract_creates_pain_points(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(extract_mod, "llm", _FakeLLM())

    with SessionLocal() as db:
        cluster = Cluster(
            label="csv batch / processing",
            size=3,
            lang_primary="zh",
        )
        db.add(cluster)
        db.flush()

        for i in range(3):
            db.add(
                RawSignal(
                    source="v2ex",
                    source_item_id=f"ex-{i}",
                    text="求一个能批量切 CSV 的工具，太麻烦了",
                    title=f"批量切 CSV {i}",
                    lang="zh",
                    score=10 - i,
                    collected_at=datetime.now(timezone.utc),
                    processed=False,
                    cluster_id=cluster.id,
                )
            )
        db.commit()
        cluster_id = cluster.id

        stats = await extract_mod.run_extract(db, max_clusters=5)
        assert stats.clusters_seen >= 1
        assert stats.pain_points_inserted >= 2

        pps = db.query(PainPoint).filter(PainPoint.cluster_id == cluster_id).all()
        assert len(pps) >= 2
        # source_signal_ids fallback worked (empty list -> first signal id)
        assert all(pp.source_signal_ids for pp in pps)

        # Re-run should skip this cluster (already has PainPoints).
        stats2 = await extract_mod.run_extract(db, max_clusters=5)
        assert stats2.clusters_processed == 0
