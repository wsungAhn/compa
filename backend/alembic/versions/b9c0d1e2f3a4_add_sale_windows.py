"""add sale_windows table

시간축(ISO 주차) 슬롯에 브랜드·명목·할인폭·출처를 붙인다.
설계: docs/design-sale-windows-2026-08-06.md

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sale_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("iso_year", sa.Integer(), nullable=False),
        sa.Column("iso_week", sa.Integer(), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=True),
        sa.Column("brand", sa.String(length=120), nullable=False),
        sa.Column("event_name", sa.String(length=255), nullable=True),
        sa.Column("discount_pct", sa.Float(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column(
            "scope",
            sa.Enum("sitewide", "category", "item", "unknown", name="sale_scope"),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("retailer", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True),
        sa.Column(
            "source",
            sa.Enum("youtube_timing", "slickdeals", "reddit", "own_observation", name="sale_window_source"),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("is_estimate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("corroborations", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("recurrence_key", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sale_windows_slot", "sale_windows", ["iso_year", "iso_week", "brand"])
    op.create_index("ix_sale_windows_recurrence", "sale_windows", ["recurrence_key", "iso_year"])
    op.create_index("ix_sale_windows_brand_week", "sale_windows", ["brand", "iso_week"])
    # 같은 출처의 같은 URL을 두 번 기록하지 않는다(주기 실행 시 중복 방지).
    op.create_index(
        "ux_sale_windows_source_url", "sale_windows", ["source", "source_url"], unique=True,
        postgresql_where=sa.text("source_url IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("sale_windows")
    op.execute("DROP TYPE IF EXISTS sale_scope")
    op.execute("DROP TYPE IF EXISTS sale_window_source")
