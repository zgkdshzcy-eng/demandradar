"""Registered users (paying or free)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._mixins import IdMixin, TimestampMixin


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # D15: opt-out flag. Set when the user clicks the unsubscribe link in any
    # transactional or newsletter email. Newsletter dispatcher skips users with
    # a non-null value here.
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # D12: Stripe customer link. Created lazily on first checkout.
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )

    # D18: preferred locale (`"en"` | `"zh"` | NULL=default). Set on first
    # signup from the explicit hint or Accept-Language header. Used by the
    # newsletter dispatcher and transactional email composers.
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # D13: Referral programme. `referral_code` is generated on first use; the
    # FK back to users tracks who invited this user.
    referral_code: Mapped[str | None] = mapped_column(
        String(16), nullable=True, unique=True
    )
    referred_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
