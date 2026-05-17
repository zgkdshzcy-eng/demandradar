"""Unified LLM client with primary (DeepSeek) + fallback (OpenAI) + verifier (Anthropic).

Usage:
    from app.core.llm import llm
    text = await llm.complete("...prompt...")

Features:
- Async only.
- Automatic retry with exponential backoff.
- Fallback chain: DeepSeek -> OpenAI -> raise.
- Cost accounting (in-memory; replace with Redis counter in production).
- JSON mode helper for structured outputs.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import logger
from app.core.llm_router import (
    BudgetExceededError as _RouterBudgetExceeded,
    PRICE_TABLE_CNY_PER_MTOK,
    TASK_DEFAULT_MAX_TOKENS,
    assert_within_budget as _router_assert_budget,
    chain_for_task,
    estimate_call_cost,
)


@dataclass
class LLMUsage:
    total_tokens: int = 0
    total_cost_cny: float = 0.0
    by_model: dict[str, dict[str, float]] = field(default_factory=dict)

    def add(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        total = prompt_tokens + completion_tokens
        price = PRICE_TABLE_CNY_PER_MTOK.get(model, 5.0)
        cost = total / 1_000_000 * price
        self.total_tokens += total
        self.total_cost_cny += cost
        bucket = self.by_model.setdefault(model, {"tokens": 0.0, "cost_cny": 0.0})
        bucket["tokens"] += total
        bucket["cost_cny"] += cost


usage = LLMUsage()


# Backwards-compatible alias — old call sites still `from app.core.llm import
# BudgetExceededError`. The router owns the canonical class.
BudgetExceededError = _RouterBudgetExceeded


def _check_budget(*, estimated_cost_cny: float = 0.0) -> None:
    """DB-backed pre-flight check. In-process counter is kept in sync but only
    serves as a debug aid now."""
    _router_assert_budget(estimated_cost_cny=estimated_cost_cny)


class LLMClient:
    """Multi-provider async LLM client."""

    def __init__(self) -> None:
        self._deepseek: AsyncOpenAI | None = None
        self._openai: AsyncOpenAI | None = None
        self._dashscope: AsyncOpenAI | None = None
        self._anthropic = None  # lazy

    # ---- providers ----
    @property
    def deepseek(self) -> AsyncOpenAI | None:
        if not settings.deepseek_api_key:
            return None
        if self._deepseek is None:
            self._deepseek = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
        return self._deepseek

    @property
    def openai(self) -> AsyncOpenAI | None:
        if not settings.openai_api_key:
            return None
        if self._openai is None:
            self._openai = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        return self._openai

    @property
    def dashscope(self) -> AsyncOpenAI | None:
        if not settings.dashscope_api_key:
            return None
        if self._dashscope is None:
            self._dashscope = AsyncOpenAI(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
            )
        return self._dashscope

    def _client_for_provider(self, name: str) -> AsyncOpenAI | None:
        """Map a provider name from the router into a live client (or None).
        Anthropic isn't OpenAI-compatible so we treat it as 'unsupported here'
        and fall through. (A future addition can wire it via Anthropic SDK.)"""
        if name == "deepseek":
            return self.deepseek
        if name == "openai":
            return self.openai
        if name == "dashscope":
            return self.dashscope
        return None

    @property
    def anthropic(self):  # type: ignore[no-untyped-def]
        if not settings.anthropic_api_key:
            return None
        if self._anthropic is None:
            from anthropic import AsyncAnthropic

            self._anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._anthropic

    # ---- core ----
    async def _call_openai_compat(
        self,
        client: AsyncOpenAI,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        json_mode: bool = False,
        max_tokens: int | None = None,
        purpose: str = "generic",
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.perf_counter()
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                resp = await client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        u = resp.usage
        prompt_t = u.prompt_tokens if u else 0
        completion_t = u.completion_tokens if u else 0
        if u:
            usage.add(model, prompt_t, completion_t)
        content = resp.choices[0].message.content or ""

        # Best-effort persistent log; never fail the call because of logging.
        try:
            _persist_usage(
                provider=provider, model=model,
                prompt_tokens=prompt_t, completion_tokens=completion_t,
                latency_ms=latency_ms, success=True, error=None,
                purpose=purpose,
            )
        except Exception:  # noqa: BLE001
            pass

        return content

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        json_mode: bool = False,
        max_tokens: int | None = None,
        prefer: str = "deepseek",
        task: str | None = None,
        purpose: str = "generic",
    ) -> str:
        """High-level completion. Returns plain text (or JSON string when json_mode=True).

        D17 routing:
        - If `task` is set, the chain comes from `chain_for_task(task)`.
        - Otherwise we fall back to the historical `prefer=` knob (deepseek
          first vs openai first), preserving legacy callers.
        - DB-backed budget guard runs *before* the call, with an upper-bound
          cost estimate so we never blow past the daily cap by more than one
          completion's worth.
        """
        # Resolve chain.
        if task is not None:
            chain_specs = chain_for_task(task)
            default_max = TASK_DEFAULT_MAX_TOKENS.get(task, 1024)
        else:
            # legacy prefer= path — synthesise the equivalent task chain.
            t = "generic" if prefer == "deepseek" else "verify"
            chain_specs = chain_for_task(t)
            default_max = TASK_DEFAULT_MAX_TOKENS["generic"]
        if not chain_specs:
            raise RuntimeError("no LLM provider configured (set DEEPSEEK_/OPENAI_/DASHSCOPE_ keys)")

        effective_max = max_tokens or default_max
        # Pre-flight budget check using the cheapest model in the chain (worst
        # case — that's the one we'll hit first).
        primary_model = chain_specs[0][2]
        est = estimate_call_cost(
            model=primary_model,
            prompt_chars=len(prompt) + (len(system) if system else 0),
            max_tokens=effective_max,
        )
        _check_budget(estimated_cost_cny=est)

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_err: Exception | None = None
        for name, _api_key, model in chain_specs:
            client = self._client_for_provider(name)
            if client is None:
                continue
            t0 = time.perf_counter()
            try:
                out = await self._call_openai_compat(
                    client, name, model, messages,
                    temperature=temperature, json_mode=json_mode,
                    max_tokens=effective_max, purpose=purpose,
                )
                logger.debug(
                    "LLM ok provider={} model={} task={} ms={:.0f} cost_cny={:.4f}",
                    name, model, task or "-", (time.perf_counter() - t0) * 1000,
                    usage.total_cost_cny,
                )
                return out
            except Exception as exc:
                logger.warning(
                    "LLM fail provider={} model={} task={} err={}",
                    name, model, task or "-", exc,
                )
                try:
                    _persist_usage(
                        provider=name, model=model,
                        prompt_tokens=0, completion_tokens=0,
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                        success=False, error=str(exc)[:500],
                        purpose=purpose,
                    )
                except Exception:  # noqa: BLE001
                    pass
                last_err = exc
                continue
        raise RuntimeError(f"All LLM providers failed: {last_err}")

    async def complete_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        task: str | None = None,
        purpose: str = "generic",
        max_tokens: int | None = None,
    ) -> Any:
        raw = await self.complete(
            prompt, system=system, temperature=temperature, json_mode=True,
            task=task, purpose=purpose, max_tokens=max_tokens,
        )
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Best-effort: extract first {...} or [...] block.
            for opener, closer in (("{", "}"), ("[", "]")):
                i = raw.find(opener)
                j = raw.rfind(closer)
                if i != -1 and j != -1 and j > i:
                    try:
                        return json.loads(raw[i : j + 1])
                    except json.JSONDecodeError:
                        continue
            raise


def _persist_usage(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    success: bool,
    error: str | None,
    purpose: str = "generic",
) -> None:
    """Write one row into llm_usage_logs. Imports are local to avoid cycles."""
    from app.db.session import SessionLocal
    from app.models.llm_usage_log import LLMUsageLog

    total = prompt_tokens + completion_tokens
    price = PRICE_TABLE_CNY_PER_MTOK.get(model, 5.0)
    cost = total / 1_000_000 * price
    with SessionLocal() as db:
        db.add(
            LLMUsageLog(
                provider=provider,
                model=model,
                purpose=purpose,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
                cost_cny=cost,
                latency_ms=latency_ms,
                success=success,
                error=error,
            )
        )
        db.commit()


llm = LLMClient()


async def _smoke() -> None:  # pragma: no cover
    out = await llm.complete("Say 'pong' in one word.")
    print(out)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_smoke())
