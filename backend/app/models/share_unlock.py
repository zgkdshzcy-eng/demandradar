"""Share-to-unlock: viral growth via social sharing.

A user shares a brief/painpoint link; when a new visitor signs up through that
link, both the sharer and the new user receive one free brief unlock.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class ShareUnlock(Base, IdMixin, TimestampMixin):
    __tablename__ = "share_unlocks"
    __table_args__ = (
        UniqueConstraint("share_token", name="uq_share_unlocks_token"),
    )

    sharer_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    share_token: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True
    )
    brief_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("briefs.id", ondelete="SET NULL"), nullable=True
    )
    pain_point_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("pain_points.id", ondelete="SET NULL"), nullable=True
    )
    platform: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # twitter, xiaohongshu, wechat, etc.
    claimed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sharer_rewarded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    claimer_rewarded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
