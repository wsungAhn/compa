"""add platform_product_ids

Revision ID: 9b8c7d6e5f4a
Revises: 857dd6abfb35
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b8c7d6e5f4a"
down_revision: Union[str, Sequence[str], None] = "857dd6abfb35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_product_ids",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "product_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform_id", sa.UUID(as_uuid=True), sa.ForeignKey("platforms.id"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("id_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("platform_id", "external_id", name="uq_platform_product_ids_platform_external"),
    )
    op.create_index("ix_platform_product_ids_product_id", "platform_product_ids", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_platform_product_ids_product_id", table_name="platform_product_ids")
    op.drop_table("platform_product_ids")
