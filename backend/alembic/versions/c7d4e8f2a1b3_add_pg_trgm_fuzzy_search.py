"""add pg_trgm extension and fuzzy search indexes

Revision ID: c7d4e8f2a1b3
Revises: a3f8e1d2c905
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c7d4e8f2a1b3'
down_revision: Union[str, Sequence[str], None] = 'a3f8e1d2c905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pg_trgm 확장 활성화 (trigram similarity 검색)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN 인덱스 — ILIKE "%q%" 와 similarity() 둘 다 사용
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_name_kr_trgm
        ON products USING gin (name_kr gin_trgm_ops)
        WHERE deleted_at IS NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_products_name_en_trgm
        ON products USING gin (name_en gin_trgm_ops)
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_products_name_kr_trgm")
    op.execute("DROP INDEX IF EXISTS idx_products_name_en_trgm")
    # Extension은 공유 리소스이므로 DROP 하지 않음
