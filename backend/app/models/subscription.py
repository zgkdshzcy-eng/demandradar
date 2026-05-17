"""Paid subscriptions (weekly report etc.)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class Subscription(Base, IdMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(32), nullable=False)  # weekly_basic | weekly_pro | brief_oneoff
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )  # active | canceled | expired | refunded
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="wechat")  # wechat | stripe
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount_cny: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # D12: Stripe linkage. NULL when the row was created via a redeem code.
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    stripe_session_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )
    # For brief_oneoff we record the unlocked brief id directly (in addition
    # to the legacy `provider_ref="brief:{id}"` convention used by D10).
    brief_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subscriptions")  # noqa: F821
