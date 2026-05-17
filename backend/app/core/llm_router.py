"""D17 LLM provider router + DB-backed daily budget guard.

What this gives the rest of the app:

1. **Task-aware fallback chains**. Different tasks have different cost/latency
   trade-offs:

       extract  -> cheap models first (deepseek-chat -> openai gpt-4o-mini)
       score    -> same; scoring is short
       brief    -> still cheap-first but allow longer context
       verify   -> anthropic if available; otherwise openai
       generic  -> deepseek -> openai

   Use :func:`chain_for_task` to materialise a list of (provider, client, model)
   triples.

2. **DB-backed daily budget**. We previously only checked an in-process
   counter, which doesn't survive worker restarts and isn't shared between
   the api + worker containers. :func:`today_spend_cny` queries
   ``llm_usage_logs`` for the current UTC day; :func:`assert_within_budget`
   raises :class:`BudgetExceededError` *before* a call is made.

3. **Cost estimation** for the pre-flight check. We don't know exact
   completion length, but a small upper-bound (`max_tokens` if provided, else
   a per-task default) is enough to keep us from blowing through the cap.

This module deliberately has zero hard imports of `app.core.llm` to avoid an
import cycle — the legacy LLMClient imports from us, not the other way round.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import TYPE_CHECKING, Iterable

from sqlalchemy import func, select

from app.core.config import settings
from app.core.logging import logger

if TYPE_CHECKING:
    from openai import AsyncOpenAI


# ---------- pricing ----------

# CNY per 1M tokens, prompt + completion averaged. Update yearly.
PRICE_TABLE_CNY_PER_MTOK: dict[str, float] = {
    # DeepSeek
    "deepseek-chat": 2.0,
    "deepseek-coder": 2.0,
    # OpenAI
    "gpt-4o-mini": 4.5,
    "gpt-4o": 35.0,
    "gpt-4.1-mini": 4.5,
    # Anthropic
    "claude-sonnet-4-5": 30.0,
    "claude-haiku-4": 6.0,
    # Aliyun DashScope (qwen). Optional fourth provider.
    "qwen-plus": 4.0,
    "qwen-max": 20.0,
}
DEFAULT_PRICE = 5.0  # used when a model isn't in the table


def cost_for(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = PRICE_TABLE_CNY_PER_MTOK.get(model, DEFAULT_PRICE)
    return (prompt_tokens + completion_tokens) / 1_000_000 * price


# ---------- task -> provider chain ----------

# (provider name, settings attr name for client, settings attr for model)
ProviderRef = tuple[str, str, str]

_DS: ProviderRef = ("deepseek", "deepseek_api_key", "deepseek_model")
_OA: ProviderRef = ("openai", "openai_api_key", "openai_model")
_AN: ProviderRef = ("anthropic", "anthropic_api_key", "anthropic_model")
_DASH: ProviderRef = ("dashscope", "dashscope_api_key", "dashscope_model")

# Order = preferred → fallback. We always favour the cheap provider first.
TASK_CHAINS: dict[str, list[ProviderRef]] = {
    "extract": [_DS, _OA, _DASH],
    "score":   [_DS, _OA, _DASH],
    "brief":   [_DS, _OA, _DASH],
    "verify":  [_AN, _OA, _DS],   # quality-sensitive
    "generic": [_DS, _OA, _DASH, _AN],
}

# Soft per-task max-completion budget (tokens). Used both as a sanity cap
# when the caller doesn't pass one, and for the budget pre-check.
TASK_DEFAULT_MAX_TOKENS: dict[str, int] = {
    "extract": 1024,
    "score":   512,
    "brief":   4096,
    "verify":  1024,
    "generic": 1024,
}


def _resolve_provider(ref: ProviderRef) -> tuple[str, str, str] | None:
    """Materialise a provider ref into (name, api_key, model). None when key empty."""
    name, key_attr, model_attr = ref
    api_key = getattr(settings, key_attr, "") or ""
    model = getattr(settings, model_attr, "") or ""
    if not api_key or not model:
        return None
    return name, api_key, model


def chain_for_task(task: str) -> list[tuple[str, str, str]]:
    """Return a list of (provider_name, api_key, model) triples for `task`,
    skipping providers without credentials. Order = preferred first.
    """
    refs = TASK_CHAINS.get(task) or TASK_CHAINS["generic"]
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for r in refs:
        resolved = _resolve_provider(r)
        if resolved is None:
            continue
        if resolved[0] in seen:
            continue
        seen.add(resolved[0])
        out.append(resolved)
    return out


# ---------- DB-backed budget ----------

class BudgetExceededError(RuntimeError):
    """Raised when today's LLM spend has hit ``LLM_DAILY_BUDGET_CNY``."""


def _utc_today_start() -> datetime:
    now = datetime.now(tz=timezone.utc)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def today_spend_cny(db=None) -> float:
    """Sum of `llm_usage_logs.cost_cny` for the current UTC day. Defaults to
    opening a short-lived session so callers don't have to plumb one through.
    """
    from app.db.session import SessionLocal
    from app.models.llm_usage_log import LLMUsageLog

    started = _utc_today_start()
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        total = db.scalar(
            select(func.coalesce(func.sum(LLMUsageLog.cost_cny), 0.0))
            .where(LLMUsageLog.created_at >= started)
        )
        return float(total or 0.0)
    finally:
        if own_session:
            db.close()


@dataclass
class BudgetStatus:
    spent_cny: float
    limit_cny: float

    @property
    def remaining_cny(self) -> float:
        return max(0.0, self.limit_cny - self.spent_cny)

    @property
    def used_pct(self) -> float:
        if self.limit_cny <= 0:
            return 0.0
        return min(100.0, self.spent_cny / self.limit_cny * 100.0)

    @property
    def over(self) -> bool:
        return self.spent_cny >= self.limit_cny


def budget_status() -> BudgetStatus:
    return BudgetStatus(
        spent_cny=today_spend_cny(), limit_cny=float(settings.llm_daily_budget_cny)
    )


def assert_within_budget(*, estimated_cost_cny: float = 0.0) -> None:
    """Raise BudgetExceededError if today's spend (+ estimate) hits the cap.
    `estimated_cost_cny=0` is fine: it acts as a strict <= check on the cap.
    """
    spent = today_spend_cny()
    cap = float(settings.llm_daily_budget_cny)
    if cap <= 0:  # disabled
        return
    if spent + estimated_cost_cny >= cap:
        raise BudgetExceededError(
            f"daily LLM budget exhausted: spent {spent:.2f} + est {estimated_cost_cny:.2f} "
            f">= cap {cap:.2f} CNY"
        )


def estimate_call_cost(
    *,
    model: str,
    prompt_chars: int,
    max_tokens: int,
) -> float:
    """Cheap upper-bound estimate. We approximate prompt tokens as
    ``prompt_chars / 3`` (mixed zh/en) and completion tokens as `max_tokens`.
    """
    prompt_tokens = max(1, prompt_chars // 3)
    return cost_for(model, prompt_tokens, max_tokens)


# ---------- breakdown for admin dashboard ----------

@dataclass
class ProviderSpend:
    provider: str
    model: str
    calls: int
    success: int
    failures: int
    tokens: int
    cost_cny: float


def by_provider_today() -> list[ProviderSpend]:
    """Per (provider, model) breakdown for today, success vs failure counts."""
    from app.db.session import SessionLocal
    from app.models.llm_usage_log import LLMUsageLog

    started = _utc_today_start()
    out: list[ProviderSpend] = []
    with SessionLocal() as db:
        rows = db.execute(
            select(
                LLMUsageLog.provider,
                LLMUsageLog.model,
                func.count(),
                func.sum(func.coalesce(LLMUsageLog.total_tokens, 0)),
                func.sum(func.coalesce(LLMUsageLog.cost_cny, 0.0)),
            )
            .where(LLMUsageLog.created_at >= started)
            .group_by(LLMUsageLog.provider, LLMUsageLog.model)
        ).all()
        success_map = dict(
            db.execute(
                select(
                    LLMUsageLog.provider,
                    func.count(),
                )
                .where(LLMUsageLog.created_at >= started)
                .where(LLMUsageLog.success.is_(True))
                .group_by(LLMUsageLog.provider)
            ).all()
        )
    for provider, model, n, tokens, cost in rows:
        succ = int(success_map.get(provider, 0))
        out.append(
            ProviderSpend(
                provider=str(provider),
                model=str(model),
                calls=int(n),
                success=succ if succ <= int(n) else int(n),
                failures=max(0, int(n) - succ if succ <= int(n) else 0),
                tokens=int(tokens or 0),
                cost_cny=float(cost or 0.0),
            )
        )
    return out


__all__ = [
    "BudgetExceededError",
    "BudgetStatus",
    "PRICE_TABLE_CNY_PER_MTOK",
    "ProviderSpend",
    "TASK_CHAINS",
    "TASK_DEFAULT_MAX_TOKENS",
    "assert_within_budget",
    "budget_status",
    "by_provider_today",
    "chain_for_task",
    "cost_for",
    "estimate_call_cost",
    "today_spend_cny",
]
