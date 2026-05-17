"""user auth + billing fields

Revision ID: 0004_user_auth_billing
Revises: 0003_weekly_reports
Create Date: 2026-05-06

- adds composite (user_id, status) index on subscriptions for entitlement lookup
- adds last_login_at to users
- adds redeem_codes table to record one-time use of offline-issued codes
  (so the same code can't be redeemed twice)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_auth_billing"
down_revision: Union[str, None] = "0003_weekly_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_subscriptions_user_status", "subscriptions", ["user_id", "status"]
    )

    op.create_table(
        "redeem_codes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("nonce", sa.String(32), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("brief_id", sa.BigInteger, nullable=True),
        sa.Column(
            "redeemed_at",
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
        sa.UniqueConstraint("nonce", name="uq_redeem_codes_nonce"),
    )
    op.create_index("ix_redeem_codes_user_id", "redeem_codes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_redeem_codes_user_id", table_name="redeem_codes")
    op.drop_table("redeem_codes")
    op.drop_index("ix_subscriptions_user_status", table_name="subscriptions")
    op.drop_column("users", "last_login_at")
