"""Structured pain points extracted by the LLM analyzer."""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class PainPoint(Base, IdMixin, TimestampMixin):
    __tablename__ = "pain_points"
    __table_args__ = (
        Index("ix_pain_total_score", "total_score"),
        Index("ix_pain_go_no_go", "go_no_go"),
    )

    cluster_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True, index=True
    )

    pain: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_user: Mapped[str | None] = mapped_column(String(255), nullable=True)

    frequency_signal: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    emotion: Mapped[str] = mapped_column(String(16), nullable=False, default="neutral")
    willingness_to_pay_signal: Mapped[str] = mapped_column(
        String(16), nullable=False, default="weak"
    )
    diy_workaround: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_quote: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # IDs of RawSignal rows used as evidence (denormalized for fast lookup)
    source_signal_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    # 10-dim scoring (filled by scorer module)
    pain_intensity: Mapped[int | None] = mapped_column(nullable=True)
    frequency: Mapped[int | None] = mapped_column(nullable=True)
    willingness_to_pay: Mapped[int | None] = mapped_column(nullable=True)
    reach_difficulty: Mapped[int | None] = mapped_column(nullable=True)
    dev_difficulty: Mapped[int | None] = mapped_column(nullable=True)
    competition: Mapped[int | None] = mapped_column(nullable=True)
    differentiation: Mapped[int | None] = mapped_column(nullable=True)
    automation_potential: Mapped[int | None] = mapped_column(nullable=True)
    virality: Mapped[int | None] = mapped_column(nullable=True)
    retention: Mapped[int | None] = mapped_column(nullable=True)

    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    go_no_go: Mapped[str | None] = mapped_column(String(8), nullable=True)  # go | watch | drop

    # D20: industry tag for benchmarking (e.g. "SaaS", "Fintech", "Health")
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
