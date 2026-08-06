"""add size_ml to sale_events

크로스 통화 매칭은 용량 대조가 전제다 — 미국은 oz, 일본은 ml로 표기해 정규화 없이는
정답 쌍까지 탈락한다(실측 0/10).
계획: docs/plan-cross-currency-matching-2026-08-06.md

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sale_events", sa.Column("size_ml", sa.Float(), nullable=True))
    op.create_index("ix_sale_events_size", "sale_events", ["size_ml"])


def downgrade() -> None:
    op.drop_index("ix_sale_events_size", table_name="sale_events")
    op.drop_column("sale_events", "size_ml")
