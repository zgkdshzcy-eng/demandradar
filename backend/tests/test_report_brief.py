"""Brief generator tests with mocked LLM."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.brief import Brief
from app.models.pain_point import PainPoint
from app.models.raw_signal import RawSignal
from app.report import project_brief as pb_mod
from app.report.pdf import md_to_html_doc, md_to_html_fragment


_FAKE_MD = """# 项目名称

## 1. 项目名称（候选）
- BatchCSV
- CSVForge
- DedupeR

## 2. 目标用户
数据分析师 / 运营; 估计 50 万 DAU 在国内 ...

## 3. 痛点描述
日常需要批量切分上百万行的 CSV，Excel 卡死。

## 4. 典型场景
- 场景 A: 出账单数据按月切分
- 场景 B: 数据科学家做 train/val 切分

## 5. 需求证据
"求一个能批量切 CSV 的工具" [^1]

## 13. 优先级评级
go - 痛点强、付费意愿明显。

## 来源
- https://example.com/post1
"""


class _FakeLLM:
    async def complete(self, prompt, *, system=None, temperature=0.35, max_tokens=4096, **kw):  # type: ignore[no-untyped-def]
        return _FAKE_MD


@pytest.mark.asyncio
async def test_run_briefs_generates_one(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(pb_mod, "llm", _FakeLLM())

    with SessionLocal() as db:
        sig = RawSignal(
            source="hn",
            source_item_id="brief-1",
            text="需要批量切 CSV 的工具",
            title="CSV pain",
            lang="zh",
            collected_at=datetime.now(timezone.utc),
        )
        db.add(sig)
        db.flush()

        pp = PainPoint(
            pain="批量切 CSV 太慢",
            scenario="数据分析师每天手工切",
            target_user="数据分析师",
            frequency_signal="high",
            emotion="anxiety",
            willingness_to_pay_signal="strong",
            source_signal_ids=[sig.id],
            pain_intensity=5, frequency=5, willingness_to_pay=5,
            reach_difficulty=4, dev_difficulty=4, competition=3,
            differentiation=4, automation_potential=5, virality=3, retention=3,
            total_score=85.0,
            go_no_go="go",
            rationale="strong fit",
        )
        db.add(pp)
        db.commit()

        from app.report.project_brief import run_briefs

        stats = await run_briefs(db, max_briefs=5, min_score=70)
        assert stats.eligible == 1
        assert stats.generated == 1

        b = db.query(Brief).filter(Brief.pain_point_id == pp.id).one()
        assert "项目名称" in b.title
        assert b.markdown.startswith("# 项目名称")

        # Re-run skips because brief already exists for this pp.
        stats2 = await run_briefs(db, max_briefs=5, min_score=70)
        assert stats2.eligible == 0


def test_md_to_html_renders_headings_and_lists() -> None:
    html = md_to_html_fragment("# T\n\n- a\n- b\n")
    # python-markdown auto-injects id=... on headings; tolerate either form.
    assert ("<h1>T</h1>" in html) or ("<h1 " in html and ">T</h1>" in html)
    assert "<li>a</li>" in html


def test_md_to_html_doc_has_full_skeleton() -> None:
    doc = md_to_html_doc("# Hi", title="Demo")
    assert doc.startswith("<!doctype html>")
    assert "<title>Demo</title>" in doc
    assert ("<h1>Hi</h1>" in doc) or ("<h1 " in doc and ">Hi</h1>" in doc)


# ---------- API tests ----------
def test_briefs_list_and_locked_preview(client: TestClient) -> None:
    r = client.get("/api/briefs?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    item = body["items"][0]
    assert "preview" in item
    # detail without unlock token: no markdown
    rd = client.get(f"/api/briefs/{item['id']}")
    assert rd.status_code == 200
    detail = rd.json()
    assert detail["unlocked"] is False
    assert "markdown" not in detail


def test_brief_markdown_paywall(client: TestClient) -> None:
    rl = client.get("/api/briefs?limit=1")
    bid = rl.json()["items"][0]["id"]
    r = client.get(f"/api/briefs/{bid}/markdown")
    assert r.status_code == 402


def test_brief_html_with_token(client: TestClient) -> None:
    from app.core.config import settings

    rl = client.get("/api/briefs?limit=1")
    bid = rl.json()["items"][0]["id"]
    r = client.get(
        f"/api/briefs/{bid}/html",
        params={"x_unlock_token": settings.app_secret_key},
    )
    assert r.status_code == 200
    # python-markdown auto-injects id="..." into headings.
    assert "<h1" in r.text or "<h2" in r.text
