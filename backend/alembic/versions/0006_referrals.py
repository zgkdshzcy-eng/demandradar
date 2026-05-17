"""referral fields on users + referral_grants ledger

Revision ID: 0006_referrals
Revises: 0005_stripe_payments
Create Date: 2026-05-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_referrals"
down_revision: Union[str, None] = "0005_stripe_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("referral_code", sa.String(16), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("referred_by_user_id", sa.BigInteger, nullable=True),
    )
    op.create_index(
        "ix_users_referral_code", "users", ["referral_code"], unique=True
    )
    op.create_foreign_key(
        "fk_users_referred_by",
        "users",
        "users",
        ["referred_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Append-only ledger of granted bonus days (so we never double-grant).
    op.create_table(
        "referral_grants",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "referrer_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referred_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(64), nullable=False),  # e.g. "first_paid"
        sa.Column("bonus_days", sa.Integer, nullable=False, default=0),
        sa.Column(
            "granted_at",
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
        sa.UniqueConstraint(
            "referrer_user_id",
            "referred_user_id",
            "trigger",
            name="uq_referral_grants_unique",
        ),
    )


def downgrade() -> None:
    op.drop_table("referral_grants")
    op.drop_constraint("fk_users_referred_by", "users", type_="foreignkey")
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_column("users", "referred_by_user_id")
    op.drop_column("users", "referral_code")
