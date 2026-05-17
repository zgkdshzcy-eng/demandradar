"""Outbound queue/log for X (Twitter), ProductHunt, and any future channel.

The same row holds both the rendered copy (so the admin dashboard can show
"what would be posted") and the post-attempt outcome (`posted` + `external_id`
or `failed` + `error`).

`status` lifecycle:
    queued  -> posted | failed | manual

`kind`:
    weekly | brief | painpoint
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class SocialPost(Base, IdMixin, TimestampMixin):
    __tablename__ = "social_posts"

    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    weekly_report_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("weekly_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    brief_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("briefs.id", ondelete="SET NULL"),
        nullable=True,
    )
    pain_point_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("pain_points.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
