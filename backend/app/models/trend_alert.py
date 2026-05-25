"""Trend alert subscriptions: users opt in to receive emails when a painpoint's
signal volume spikes week-over-week.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class TrendAlert(Base, IdMixin, TimestampMixin):
    __tablename__ = "trend_alerts"
    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_trend_alerts_user_keyword"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    keyword: Mapped[str] = mapped_column(
        String(120), nullable=False
    )
    min_score: Mapped[int] = mapped_column(
        BigInteger, default=70, nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
