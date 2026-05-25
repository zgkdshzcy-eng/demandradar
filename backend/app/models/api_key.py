"""API key for data export / monetization tier."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class ApiKey(Base, IdMixin, TimestampMixin):
    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_api_keys_hash"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    key_prefix: Mapped[str] = mapped_column(
        String(12), nullable=False
    )  # first 8 chars for display
    name: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    request_count: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
