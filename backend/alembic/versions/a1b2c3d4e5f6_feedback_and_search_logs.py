"""feedback and search_logs

Revision ID: a1b2c3d4e5f6
Revises: c7d4e8f2a1b3
Create Date: 2026-06-19 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "c7d4e8f2a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("page", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "search_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("lang", sa.String(length=8), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False),
        sa.Column("collecting", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_logs_created_at", "search_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_search_logs_created_at", table_name="search_logs")
    op.drop_table("search_logs")
    op.drop_table("feedbacks")
