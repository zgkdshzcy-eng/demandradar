"""init schema

Revision ID: 0001_init
Revises:
Create Date: 2026-05-06

Creates all DemandRadar tables and enables pgvector.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    # pgvector extension (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---------- waitlist_entries ----------
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("source", sa.String(64), nullable=False, server_default="landing"),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_waitlist_email"),
    )
    op.create_index("ix_waitlist_entries_email", "waitlist_entries", ["email"])

    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ---------- subscriptions ----------
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("provider", sa.String(32), nullable=False, server_default="wechat"),
        sa.Column("provider_ref", sa.String(128), nullable=True),
        sa.Column("amount_cny", sa.Numeric(10, 2), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_provider_ref", "subscriptions", ["provider_ref"])

    # ---------- raw_signals ----------
    op.create_table(
        "raw_signals",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_item_id", sa.String(128), nullable=False),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column("author", sa.String(120), nullable=True),
        sa.Column("lang", sa.String(8), nullable=False, server_default="unknown"),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comments_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extra", sa.JSON, nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source", "source_item_id", name="uq_raw_source_item"),
    )
    op.create_index("ix_raw_lang_collected", "raw_signals", ["lang", "collected_at"])
    op.create_index("ix_raw_source_collected", "raw_signals", ["source", "collected_at"])
    op.create_index("ix_raw_signals_processed", "raw_signals", ["processed"])
    # IVFFlat index on embedding (cosine). lists=100 is fine for <1M rows.
    op.execute(
        "CREATE INDEX ix_raw_embedding_cos ON raw_signals "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # ---------- clusters ----------
    op.create_table(
        "clusters",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("centroid", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("size", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lang_primary", sa.String(8), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ---------- pain_points ----------
    op.create_table(
        "pain_points",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("cluster_id", sa.BigInteger, sa.ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pain", sa.String(255), nullable=False),
        sa.Column("scenario", sa.String(500), nullable=True),
        sa.Column("target_user", sa.String(255), nullable=True),
        sa.Column("frequency_signal", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("emotion", sa.String(16), nullable=False, server_default="neutral"),
        sa.Column("willingness_to_pay_signal", sa.String(16), nullable=False, server_default="weak"),
        sa.Column("diy_workaround", sa.Text, nullable=True),
        sa.Column("evidence_quote", sa.String(500), nullable=True),
        sa.Column("source_signal_ids", sa.JSON, nullable=True),
        sa.Column("pain_intensity", sa.Integer, nullable=True),
        sa.Column("frequency", sa.Integer, nullable=True),
        sa.Column("willingness_to_pay", sa.Integer, nullable=True),
        sa.Column("reach_difficulty", sa.Integer, nullable=True),
        sa.Column("dev_difficulty", sa.Integer, nullable=True),
        sa.Column("competition", sa.Integer, nullable=True),
        sa.Column("differentiation", sa.Integer, nullable=True),
        sa.Column("automation_potential", sa.Integer, nullable=True),
        sa.Column("virality", sa.Integer, nullable=True),
        sa.Column("retention", sa.Integer, nullable=True),
        sa.Column("total_score", sa.Float, nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("go_no_go", sa.String(8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pain_points_cluster_id", "pain_points", ["cluster_id"])
    op.create_index("ix_pain_total_score", "pain_points", ["total_score"])
    op.create_index("ix_pain_go_no_go", "pain_points", ["go_no_go"])

    # ---------- briefs ----------
    op.create_table(
        "briefs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("pain_point_id", sa.BigInteger, sa.ForeignKey("pain_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("markdown", sa.Text, nullable=False),
        sa.Column("pdf_path", sa.String(512), nullable=True),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="paid"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_briefs_pain_point_id", "briefs", ["pain_point_id"])

    # ---------- llm_usage_logs ----------
    op.create_table(
        "llm_usage_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False, server_default="generic"),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_cny", sa.Float, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_llm_log_provider_created", "llm_usage_logs", ["provider", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_llm_log_provider_created", table_name="llm_usage_logs")
    op.drop_table("llm_usage_logs")

    op.drop_index("ix_briefs_pain_point_id", table_name="briefs")
    op.drop_table("briefs")

    op.drop_index("ix_pain_go_no_go", table_name="pain_points")
    op.drop_index("ix_pain_total_score", table_name="pain_points")
    op.drop_index("ix_pain_points_cluster_id", table_name="pain_points")
    op.drop_table("pain_points")

    op.drop_table("clusters")

    op.execute("DROP INDEX IF EXISTS ix_raw_embedding_cos")
    op.drop_index("ix_raw_signals_processed", table_name="raw_signals")
    op.drop_index("ix_raw_source_collected", table_name="raw_signals")
    op.drop_index("ix_raw_lang_collected", table_name="raw_signals")
    op.drop_table("raw_signals")

    op.drop_index("ix_subscriptions_provider_ref", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_waitlist_entries_email", table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
