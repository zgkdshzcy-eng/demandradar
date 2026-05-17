"""Waitlist entries (early subscribers before paid product launch)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class WaitlistEntry(Base, IdMixin, TimestampMixin):
    __tablename__ = "waitlist_entries"
    __table_args__ = (UniqueConstraint("email", name="uq_waitlist_email"),)

    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="landing")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # D15: opt-out flag. The newsletter dispatcher skips entries where this is
    # set; we keep the row for auditing instead of deleting it.
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # D18: preferred locale (`"en"` | `"zh"` | NULL=default). The newsletter
    # dispatcher uses this to pick the bilingual template variant.
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)
