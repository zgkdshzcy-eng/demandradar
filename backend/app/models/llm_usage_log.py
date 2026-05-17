"""Persistent LLM usage / cost log for daily budget enforcement and audit."""
from __future__ import annotations

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class LLMUsageLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "llm_usage_logs"
    __table_args__ = (
        Index("ix_llm_log_provider_created", "provider", "created_at"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, default="generic")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_cny: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
