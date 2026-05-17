"""newsletter dispatches, social posts, unsubscribe flag

Revision ID: 0007_newsletter_social
Revises: 0006_referrals
Create Date: 2026-05-07
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_newsletter_social"
down_revision: Union[str, None] = "0006_referrals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1. unsubscribe flag ---------------------------------------------
    op.add_column(
        "users",
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "waitlist_entries",
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ---- 2. email_dispatches: per-recipient per-issue send log -----------
    op.create_table(
        "email_dispatches",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        # campaign identifier — for weekly: "weekly:<issue_no>"
        sa.Column("campaign", sa.String(80), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "weekly_report_id",
            sa.BigInteger,
            sa.ForeignKey("weekly_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, default="sent"),
        # status: pending | sent | failed | skipped (unsubscribed/bounced)
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, default=1),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), nullable=True
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
            "campaign", "email", name="uq_email_dispatches_campaign_email"
        ),
    )

    # ---- 3. social_posts: outbound queue + log for X / PH / RSS ----------
    op.create_table(
        "social_posts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        # platform: "x" | "producthunt" | "rss"
        sa.Column("platform", sa.String(32), nullable=False, index=True),
        # status: queued | posted | failed | manual
        sa.Column("status", sa.String(20), nullable=False, default="queued"),
        # category: "weekly" | "brief" | "painpoint"
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "weekly_report_id",
            sa.BigInteger,
            sa.ForeignKey("weekly_reports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "brief_id",
            sa.BigInteger,
            sa.ForeignKey("briefs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "pain_point_id",
            sa.BigInteger,
            sa.ForeignKey("pain_points.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        # external_id is the platform-side post id (tweet id, ph submission id)
        sa.Column("external_id", sa.String(120), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column(
            "posted_at", sa.DateTime(timezone=True), nullable=True
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
    )
    op.create_index(
        "ix_social_posts_status",
        "social_posts",
        ["platform", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_social_posts_status", table_name="social_posts")
    op.drop_table("social_posts")
    op.drop_table("email_dispatches")
    op.drop_column("waitlist_entries", "unsubscribed_at")
    op.drop_column("users", "unsubscribed_at")
