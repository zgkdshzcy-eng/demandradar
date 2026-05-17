"""Append-only ledger of every Stripe webhook event we processed.

The unique `event_id` constraint is what makes our webhook handler idempotent:
Stripe is allowed to retry the same event many times — we just upsert and
short-circuit on the second attempt.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class PaymentEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_payment_events_event_id"),)

    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    subscription_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
