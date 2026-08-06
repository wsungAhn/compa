"""add slickdeals to social_platform enum

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE social_platform ADD VALUE IF NOT EXISTS 'slickdeals'")


def downgrade() -> None:
    op.execute("DELETE FROM social_posts WHERE platform = 'slickdeals'")
