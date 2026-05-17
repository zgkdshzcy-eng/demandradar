"""Scorer tests with mocked LLM."""
from __future__ import annotations

import pytest

from app.db.session import SessionLocal
from app.models.pain_point import PainPoint
from app.scorer import score as score_mod
from app.scorer.score import _weighted_total, run_score


class _FakeLLM:
    async def complete_json(self, prompt, *, system=None, temperature=0.1, **kw):  # type: ignore[no-untyped-def]
        return {
            "pain_intensity": 5,
            "frequency": 4,
            "willingness_to_pay": 5,
            "reach_difficulty": 4,
            "dev_difficulty": 4,
            "competition": 3,
            "differentiation": 4,
            "automation_potential": 5,
            "virality": 3,
            "retention": 3,
            "rationale": "高付费意愿+高自动化潜力",
            "go_no_go": "go",
        }


class _LowLLM:
    async def complete_json(self, prompt, *, system=None, temperature=0.1, **kw):  # type: ignore[no-untyped-def]
        # Low scores; LLM returns 'drop'.
        return {col: 1 for col in (
            "pain_intensity", "frequency", "willingness_to_pay",
            "reach_difficulty", "dev_difficulty", "competition",
            "differentiation", "automation_potential", "virality", "retention",
        )}


def test_weighted_total_full_5() -> None:
    scores = {col: 5 for col in (
        "pain_intensity", "frequency", "willingness_to_pay",
        "reach_difficulty", "dev_difficulty", "competition",
        "differentiation", "automation_potential", "virality", "retention",
    )}
    assert _weighted_total(scores) == 100.0


def test_weighted_total_full_1() -> None:
    scores = {col: 1 for col in (
        "pain_intensity", "frequency", "willingness_to_pay",
        "reach_difficulty", "dev_difficulty", "competition",
        "differentiation", "automation_potential", "virality", "retention",
    )}
    assert _weighted_total(scores) == 20.0


@pytest.mark.asyncio
async def test_run_score_high(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(score_mod, "llm", _FakeLLM())

    with SessionLocal() as db:
        pp = PainPoint(
            pain="无法批量处理大文件",
            frequency_signal="high",
            emotion="anxiety",
            willingness_to_pay_signal="strong",
        )
        db.add(pp)
        db.commit()
        pp_id = pp.id

        stats = await run_score(db, limit=10)
        assert stats.scored == 1
        assert stats.errors == 0

        db.refresh(pp)
        assert pp.total_score is not None
        assert pp.total_score > 70  # high tier
        assert pp.go_no_go == "go"
        assert pp.pain_intensity == 5
        assert pp.rationale and "付费" in pp.rationale

        # Re-run is no-op
        stats2 = await run_score(db, limit=10)
        assert stats2.seen == 0
        # cleanup so other tests don't rely on this row
        db.delete(pp)
        db.commit()
        _ = pp_id  # silence


@pytest.mark.asyncio
async def test_run_score_low_auto_go_no_go(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # If LLM omits go_no_go, scorer auto-derives from total_score.
    class _NoGoLLM:
        async def complete_json(self, prompt, *, system=None, temperature=0.1, **kw):  # type: ignore[no-untyped-def]
            return {col: 1 for col in (
                "pain_intensity", "frequency", "willingness_to_pay",
                "reach_difficulty", "dev_difficulty", "competition",
                "differentiation", "automation_potential", "virality", "retention",
            )}  # no go_no_go field

    monkeypatch.setattr(score_mod, "llm", _NoGoLLM())

    with SessionLocal() as db:
        pp = PainPoint(pain="边缘小痛点")
        db.add(pp)
        db.commit()
        await run_score(db, limit=10)
        db.refresh(pp)
        assert pp.total_score == 20.0
        assert pp.go_no_go == "drop"
        db.delete(pp)
        db.commit()
