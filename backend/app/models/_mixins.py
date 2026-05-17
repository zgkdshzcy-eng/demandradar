"""Common column mixins."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Postgres gets BIGINT (room to grow); SQLite gets INTEGER, which it treats as
# a ROWID alias so autoincrement actually works in the test suite.
_PK = BigInteger().with_variant(Integer(), "sqlite")


class IdMixin:
    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
