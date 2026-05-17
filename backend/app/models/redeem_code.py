"""Record of redeem codes that have actually been used.

The signed redeem code (issued via CLI) carries everything needed to grant
a subscription, but we still persist a one-shot record so the same nonce
cannot be redeemed twice.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class RedeemCode(Base, IdMixin, TimestampMixin):
    __tablename__ = "redeem_codes"
    __table_args__ = (UniqueConstraint("nonce", name="uq_redeem_codes_nonce"),)

    nonce: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brief_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
