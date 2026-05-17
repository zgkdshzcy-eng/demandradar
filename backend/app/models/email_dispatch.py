"""Per-recipient send log for the weekly newsletter (and any future campaigns).

A row is upserted when we attempt to send. The unique (campaign,email) index
makes redispatch safe — calling `dispatch_weekly` twice in a row is a no-op
for already-sent rows.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class EmailDispatch(Base, IdMixin, TimestampMixin):
    __tablename__ = "email_dispatches"
    __table_args__ = (
        UniqueConstraint(
            "campaign", "email", name="uq_email_dispatches_campaign_email"
        ),
    )

    campaign: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    weekly_report_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("weekly_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
