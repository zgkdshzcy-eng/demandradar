"""Semantic clusters formed from raw signals (HDBSCAN over embeddings)."""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin
from app.models.raw_signal import EMBEDDING_DIM


class Cluster(Base, IdMixin, TimestampMixin):
    __tablename__ = "clusters"

    label: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    centroid: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Aggregated language distribution etc.
    lang_primary: Mapped[str] = mapped_column(String(8), default="unknown", nullable=False)
