"""add raw_signals.cluster_id

Revision ID: 0002_raw_cluster_fk
Revises: 0001_init
Create Date: 2026-05-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_raw_cluster_fk"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "raw_signals",
        sa.Column("cluster_id", sa.BigInteger, nullable=True),
    )
    op.create_foreign_key(
        "fk_raw_signals_cluster",
        "raw_signals",
        "clusters",
        ["cluster_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_raw_signals_cluster_id", "raw_signals", ["cluster_id"])


def downgrade() -> None:
    op.drop_index("ix_raw_signals_cluster_id", table_name="raw_signals")
    op.drop_constraint("fk_raw_signals_cluster", "raw_signals", type_="foreignkey")
    op.drop_column("raw_signals", "cluster_id")
