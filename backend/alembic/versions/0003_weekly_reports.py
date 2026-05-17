"""add weekly_reports

Revision ID: 0003_weekly_reports
Revises: 0002_raw_cluster_fk
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_weekly_reports"
down_revision: Union[str, None] = "0002_raw_cluster_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("issue_no", sa.Integer, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("markdown_full", sa.Text, nullable=False),
        sa.Column("markdown_preview", sa.Text, nullable=False),
        sa.Column("pain_point_ids", sa.JSON, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("sent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("issue_no", name="uq_weekly_issue_no"),
    )


def downgrade() -> None:
    op.drop_table("weekly_reports")
