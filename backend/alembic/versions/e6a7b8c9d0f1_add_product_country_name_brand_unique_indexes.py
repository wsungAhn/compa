"""add product country name brand unique indexes

Revision ID: e6a7b8c9d0f1
Revises: d5f6a7b8c9e0
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e6a7b8c9d0f1"
down_revision: Union[str, Sequence[str], None] = "d5f6a7b8c9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COUNTRY_COLUMNS = ("name_kr", "name_en", "name_jp", "name_cn")


def _duplicate_check_sql(column_name: str) -> str:
    return f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM products
            WHERE deleted_at IS NULL
              AND {column_name} IS NOT NULL
            GROUP BY lower({column_name}), lower(coalesce(brand, ''))
            HAVING count(*) > 1
            LIMIT 1
        ) THEN
            RAISE EXCEPTION
                'duplicate active products exist for {column_name}/brand; resolve data before adding unique index';
        END IF;
    END $$;
    """


def upgrade() -> None:
    for column_name in _COUNTRY_COLUMNS:
        op.execute(_duplicate_check_sql(column_name))
        op.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_products_{column_name}_brand_active
            ON products (lower({column_name}), lower(coalesce(brand, '')))
            WHERE deleted_at IS NULL
              AND {column_name} IS NOT NULL
        """)


def downgrade() -> None:
    for column_name in _COUNTRY_COLUMNS:
        op.execute(f"DROP INDEX IF EXISTS uq_products_{column_name}_brand_active")
