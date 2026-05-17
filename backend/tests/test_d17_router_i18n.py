"""D17 LLM router + budget guard + bilingual prompts + admin /llm-budget."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.analyzer.prompts import detect_lang, load_prompt
from app.core import llm_router as lr
from app.core.security import issue_magic_link_token
from app.db import session as db_session
from app.db.session import Base
from app.models.llm_usage_log import LLMUsageLog
from app.models.user import User


@pytest.fixture(autouse=True)
def _clean_per_test():
    yield
    with db_session.engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())


# ---------------------------------------------------------------------------
# 1. cost / chain_for_task
# ---------------------------------------------------------------------------

class TestRouter:
    def test_cost_for_known_model(self) -> None:
        # 1M tokens at deepseek = 2.0 CNY → 100k = 0.2 CNY (50/50 split)
        c = lr.cost_for("deepseek-chat", 50_000, 50_000)
        assert abs(c - 0.2) < 1e-6

    def test_cost_for_unknown_model_uses_default(self) -> None:
        c = lr.cost_for("unknown-model", 1_000_000, 0)
        assert abs(c - lr.DEFAULT_PRICE) < 1e-6

    def test_chain_skips_providers_without_keys(self, monkeypatch) -> None:
        for attr in (
            "deepseek_api_key", "openai_api_key",
            "dashscope_api_key", "anthropic_api_key",
        ):
            monkeypatch.setattr(lr.settings, attr, "", raising=False)
        assert lr.chain_for_task("extract") == []

    def test_chain_dedupes_and_orders(self, monkeypatch) -> None:
        monkeypatch.setattr(lr.settings, "deepseek_api_key", "x", raising=False)
        monkeypatch.setattr(lr.settings, "deepseek_model", "deepseek-chat", raising=False)
        monkeypatch.setattr(lr.settings, "openai_api_key", "y", raising=False)
        monkeypatch.setattr(lr.settings, "openai_model", "gpt-4o-mini", raising=False)
        monkeypatch.setattr(lr.settings, "dashscope_api_key", "", raising=False)
        chain = lr.chain_for_task("extract")
        assert [c[0] for c in chain] == ["deepseek", "openai"]

    def test_chain_unknown_task_falls_back_to_generic(self, monkeypatch) -> None:
        monkeypatch.setattr(lr.settings, "deepseek_api_key", "x", raising=False)
        monkeypatch.setattr(lr.settings, "deepseek_model", "deepseek-chat", raising=False)
        for attr in ("openai_api_key", "dashscope_api_key", "anthropic_api_key"):
            monkeypatch.setattr(lr.settings, attr, "", raising=False)
        chain = lr.chain_for_task("unknown-task")
        assert chain[0][0] == "deepseek"

    def test_estimate_call_cost_upper_bound(self) -> None:
        # 9000 prompt chars => ~3000 tokens; +1000 max → 4k tokens at 4.5/M.
        est = lr.estimate_call_cost(model="gpt-4o-mini", prompt_chars=9000, max_tokens=1000)
        # 4000/1e6 * 4.5 = 0.018
        assert abs(est - 0.018) < 1e-3


# ---------------------------------------------------------------------------
# 2. DB-backed budget
# ---------------------------------------------------------------------------

class TestBudget:
    def _seed_today(self, db, *, cost: float, provider: str = "deepseek") -> None:
        now = datetime.now(tz=timezone.utc)
        db.add(
            LLMUsageLog(
                provider=provider, model="deepseek-chat", purpose="extract",
                prompt_tokens=100, completion_tokens=200, total_tokens=300,
                cost_cny=cost, latency_ms=50, success=True,
                created_at=now, updated_at=now,
            )
        )
        db.commit()

    def _seed_yesterday(self, db, *, cost: float) -> None:
        d = datetime.now(tz=timezone.utc) - timedelta(days=1, hours=2)
        row = LLMUsageLog(
            provider="deepseek", model="deepseek-chat", purpose="extract",
            prompt_tokens=100, completion_tokens=200, total_tokens=300,
            cost_cny=cost, latency_ms=50, success=True,
        )
        # Force the row's created_at into yesterday by post-flush update.
        db.add(row)
        db.flush()
        row.created_at = d
        row.updated_at = d
        db.commit()

    def test_today_spend_only_counts_today(self) -> None:
        with db_session.SessionLocal() as db:
            self._seed_today(db, cost=0.5)
            self._seed_yesterday(db, cost=10.0)
        assert abs(lr.today_spend_cny() - 0.5) < 1e-6

    def test_assert_within_budget_passes_under_cap(self, monkeypatch) -> None:
        monkeypatch.setattr(lr.settings, "llm_daily_budget_cny", 5.0, raising=False)
        with db_session.SessionLocal() as db:
            self._seed_today(db, cost=1.0)
        # 1.0 + 0.1 estimate < 5.0
        lr.assert_within_budget(estimated_cost_cny=0.1)

    def test_assert_within_budget_raises_at_cap(self, monkeypatch) -> None:
        monkeypatch.setattr(lr.settings, "llm_daily_budget_cny", 1.0, raising=False)
        with db_session.SessionLocal() as db:
            self._seed_today(db, cost=0.95)
        with pytest.raises(lr.BudgetExceededError):
            lr.assert_within_budget(estimated_cost_cny=0.1)

    def test_assert_within_budget_no_cap_when_zero(self, monkeypatch) -> None:
        monkeypatch.setattr(lr.settings, "llm_daily_budget_cny", 0.0, raising=False)
        with db_session.SessionLocal() as db:
            self._seed_today(db, cost=99999.0)
        lr.assert_within_budget(estimated_cost_cny=99999.0)

    def test_budget_status_fields(self, monkeypatch) -> None:
        monkeypatch.setattr(lr.settings, "llm_daily_budget_cny", 10.0, raising=False)
        with db_session.SessionLocal() as db:
            self._seed_today(db, cost=2.5)
        s = lr.budget_status()
        assert s.spent_cny == pytest.approx(2.5)
        assert s.limit_cny == 10.0
        assert s.remaining_cny == pytest.approx(7.5)
        assert s.used_pct == pytest.approx(25.0)
        assert s.over is False

    def test_by_provider_today_groups(self) -> None:
        with db_session.SessionLocal() as db:
            self._seed_today(db, cost=1.0, provider="deepseek")
            self._seed_today(db, cost=2.0, provider="deepseek")
            self._seed_today(db, cost=0.5, provider="openai")
        rows = {(r.provider, r.model): r for r in lr.by_provider_today()}
        assert rows[("deepseek", "deepseek-chat")].calls == 2
        assert rows[("deepseek", "deepseek-chat")].cost_cny == pytest.approx(3.0)
        assert ("openai", "deepseek-chat") in rows


# ---------------------------------------------------------------------------
# 3. Bilingual prompts
# ---------------------------------------------------------------------------

class TestPromptsI18n:
    def test_detect_lang_zh(self) -> None:
        assert detect_lang("我需要一个工具来批量处理文件") == "zh"

    def test_detect_lang_en(self) -> None:
        assert detect_lang("I'm looking for a tool to deduplicate CSVs") == "en"

    def test_detect_lang_empty(self) -> None:
        assert detect_lang("") == "en"

    def test_load_prompt_picks_en_variant(self) -> None:
        # pain_extract.en.md exists; should be returned over the base file.
        load_prompt.cache_clear()
        sys_text, user_text = load_prompt("pain_extract", lang="en")
        assert "indie-developer investor" in sys_text
        assert "{{INPUT_JSON}}" in user_text

    def test_load_prompt_falls_back_to_base(self) -> None:
        load_prompt.cache_clear()
        # No `scoring.en.md` exists → base is returned regardless of lang.
        sys_zh, _ = load_prompt("scoring", lang="zh")
        sys_en, _ = load_prompt("scoring", lang="en")
        assert sys_zh == sys_en  # same file behind both
        assert sys_zh != ""

    def test_load_prompt_unknown_name_raises(self) -> None:
        load_prompt.cache_clear()
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt_xyz", lang="en")


# ---------------------------------------------------------------------------
# 4. /api/admin/llm-budget endpoint
# ---------------------------------------------------------------------------

class TestAdminLLMBudget:
    def _admin(self, client: TestClient, email: str) -> dict[str, str]:
        token = issue_magic_link_token(email)
        r = client.post("/api/auth/exchange", json={"token": token})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        with db_session.SessionLocal() as db:
            u = db.scalar(select(User).where(User.email == email))
            u.is_admin = True
            db.commit()
        return headers

    def test_endpoint_requires_admin(self, client: TestClient) -> None:
        token = issue_magic_link_token("noadm-d17@example.com")
        r0 = client.post("/api/auth/exchange", json={"token": token})
        h = {"Authorization": f"Bearer {r0.json()['access_token']}"}
        r = client.get("/api/admin/llm-budget", headers=h)
        assert r.status_code == 403

    def test_endpoint_returns_budget_breakdown(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(lr.settings, "llm_daily_budget_cny", 10.0, raising=False)
        with db_session.SessionLocal() as db:
            now = datetime.now(tz=timezone.utc)
            for cost, ok in [(1.0, True), (2.0, True), (0.0, False)]:
                db.add(
                    LLMUsageLog(
                        provider="deepseek", model="deepseek-chat",
                        purpose="extract", total_tokens=300,
                        cost_cny=cost, success=ok,
                        created_at=now, updated_at=now,
                    )
                )
            db.commit()
        h = self._admin(client, "adm-d17@example.com")
        r = client.get("/api/admin/llm-budget", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["limit_cny"] == 10.0
        assert body["spent_cny"] == pytest.approx(3.0)
        assert body["remaining_cny"] == pytest.approx(7.0)
        assert body["over"] is False
        assert body["by_provider"]
        # 3 calls, 2 success, 1 failure
        ds = next(r for r in body["by_provider"] if r["provider"] == "deepseek")
        assert ds["calls"] == 3
        assert ds["success"] == 2
        assert ds["failures"] == 1
        assert any(p["purpose"] == "extract" for p in body["top_purposes"])

    def test_endpoint_marks_over_when_exhausted(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(lr.settings, "llm_daily_budget_cny", 1.0, raising=False)
        with db_session.SessionLocal() as db:
            db.add(
                LLMUsageLog(
                    provider="deepseek", model="deepseek-chat",
                    purpose="brief", total_tokens=300,
                    cost_cny=1.5, success=True,
                )
            )
            db.commit()
        h = self._admin(client, "adm-d17-over@example.com")
        r = client.get("/api/admin/llm-budget", headers=h)
        body = r.json()
        assert body["over"] is True
        assert body["used_pct"] == 100.0
