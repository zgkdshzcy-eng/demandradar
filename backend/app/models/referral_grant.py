"""Idempotent ledger of referral bonuses already paid out.

Unique on (referrer, referred, trigger): we never grant the same kind of
bonus twice for the same referred user, even if their checkout succeeds
again later.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class ReferralGrant(Base, IdMixin, TimestampMixin):
    __tablename__ = "referral_grants"
    __table_args__ = (
        UniqueConstraint(
            "referrer_user_id",
            "referred_user_id",
            "trigger",
            name="uq_referral_grants_unique",
        ),
    )

    referrer_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    referred_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)
    bonus_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
