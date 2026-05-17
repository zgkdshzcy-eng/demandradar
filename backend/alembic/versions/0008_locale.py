"""add locale columns to users + waitlist_entries

Revision ID: 0008_locale
Revises: 0007_newsletter_social
Create Date: 2026-05-07

Stores the recipient's preferred locale so transactional emails (paid
confirmation, referral bonus, login welcome) and the weekly newsletter can
render in the right language. NULL is treated as "use the default" (English
post-pivot) by every reader.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_locale"
down_revision: Union[str, None] = "0007_newsletter_social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locale", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "waitlist_entries",
        sa.Column("locale", sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("waitlist_entries", "locale")
    op.drop_column("users", "locale")
