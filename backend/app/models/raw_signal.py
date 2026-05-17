"""Raw signals collected from public sources (Reddit/HN/PH/V2EX/...)."""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin

# 1024 dim matches bge-m3; switch to 1536 if using OpenAI text-embedding-3-small.
EMBEDDING_DIM = 1024


class RawSignal(Base, IdMixin, TimestampMixin):
    """A normalized record from any data source.

    Identity = (source, source_item_id). Used by collectors for upsert.
    """

    __tablename__ = "raw_signals"
    __table_args__ = (
        UniqueConstraint("source", "source_item_id", name="uq_raw_source_item"),
        Index("ix_raw_lang_collected", "lang", "collected_at"),
        Index("ix_raw_source_collected", "source", "collected_at"),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    # e.g. "reddit", "hn", "producthunt", "v2ex", "appstore"
    source_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lang: Mapped[str] = mapped_column(String(8), nullable=False, default="unknown")

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # upvotes/likes
    comments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Source-specific extra payload
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Embedding for semantic clustering (nullable until analyzer fills it)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    # Has this signal been processed by the analyzer?
    processed: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)

    # Assigned by clustering pipeline (D5).
    cluster_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("clusters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
