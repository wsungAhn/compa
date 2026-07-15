"""add social post failure state

Revision ID: d5f6a7b8c9e0
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d5f6a7b8c9e0"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "social_posts",
        sa.Column("failed", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "social_posts",
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("social_posts", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("social_posts", "last_error")
    op.drop_column("social_posts", "retry_count")
    op.drop_column("social_posts", "failed")
