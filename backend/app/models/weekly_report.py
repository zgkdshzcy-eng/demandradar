"""Weekly digest report - the recurring subscription artifact."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class WeeklyReport(Base, IdMixin, TimestampMixin):
    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("issue_no", name="uq_weekly_issue_no"),)

    issue_no: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    markdown_full: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_preview: Mapped[str] = mapped_column(Text, nullable=False)

    # PainPoint ids included, in rank order
    pain_point_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    # draft | published | sent
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
