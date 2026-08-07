"""add product match candidates

Revision ID: 857dd6abfb35
Revises: d1e2f3a4b5c6
Create Date: 2026-08-06 18:36:05.249766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '857dd6abfb35'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add product_match_candidates table for cross-currency matching candidates
    # This table stores potential matches between orphan products (JP-only) and canonical products (US/etc)
    # with pending/approved/rejected status for manual review workflow
    op.create_table(
        "product_match_candidates",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("orphan_product_id", sa.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("canonical_product_id", sa.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", name="match_candidate_status"), nullable=False, default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(50), nullable=True),
        sa.UniqueConstraint("orphan_product_id", name="uq_product_match_candidate_orphan"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("product_match_candidates")
