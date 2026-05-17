"""Generated 13-section project briefs (sellable artifact)."""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class Brief(Base, IdMixin, TimestampMixin):
    __tablename__ = "briefs"

    pain_point_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("pain_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # public | paid
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="paid")
    version: Mapped[int] = mapped_column(default=1, nullable=False)
