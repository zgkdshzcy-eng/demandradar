"""stripe payments + idempotent webhook events

Revision ID: 0005_stripe_payments
Revises: 0004_user_auth_billing
Create Date: 2026-05-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_stripe_payments"
down_revision: Union[str, None] = "0004_user_auth_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User <-> Stripe customer link.
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_users_stripe_customer_id", "users", ["stripe_customer_id"], unique=True
    )

    # Subscription <-> Stripe subscription/session link.
    op.add_column(
        "subscriptions",
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("stripe_session_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("brief_id", sa.BigInteger, nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("amount_cents", sa.Integer, nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("currency", sa.String(8), nullable=True),
    )
    op.create_index(
        "ix_subscriptions_stripe_subscription_id",
        "subscriptions",
        ["stripe_subscription_id"],
        unique=True,
    )
    op.create_index(
        "ix_subscriptions_stripe_session_id",
        "subscriptions",
        ["stripe_session_id"],
        unique=True,
    )

    # payment_events: append-only ledger for idempotent webhook processing.
    op.create_table(
        "payment_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("user_id", sa.BigInteger, nullable=True),
        sa.Column("subscription_id", sa.BigInteger, nullable=True),
        sa.Column(
            "payload",
            sa.JSON,
            nullable=True,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("event_id", name="uq_payment_events_event_id"),
    )
    op.create_index(
        "ix_payment_events_type", "payment_events", ["type"]
    )


def downgrade() -> None:
    op.drop_index("ix_payment_events_type", table_name="payment_events")
    op.drop_table("payment_events")

    op.drop_index(
        "ix_subscriptions_stripe_session_id", table_name="subscriptions"
    )
    op.drop_index(
        "ix_subscriptions_stripe_subscription_id", table_name="subscriptions"
    )
    op.drop_column("subscriptions", "currency")
    op.drop_column("subscriptions", "amount_cents")
    op.drop_column("subscriptions", "brief_id")
    op.drop_column("subscriptions", "stripe_session_id")
    op.drop_column("subscriptions", "stripe_subscription_id")

    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_customer_id")
