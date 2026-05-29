"""deduplicate sale_events and add unique index

Revision ID: a3f8e1d2c905
Revises: 9f41a20f9a7e
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a3f8e1d2c905'
down_revision: Union[str, Sequence[str], None] = '4618dbf54f38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 기존 중복 행 제거 (같은 product+platform+start_date+event_name 중 가장 오래된 행만 유지)
    op.execute("""
        WITH dupes AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY
                           product_id,
                           platform_id,
                           COALESCE(start_date, '1900-01-01'::date),
                           COALESCE(event_name, '')
                       ORDER BY created_at ASC
                   ) AS rn
            FROM sale_events
            WHERE deleted_at IS NULL
        )
        DELETE FROM sale_events
        WHERE id IN (SELECT id FROM dupes WHERE rn > 1)
    """)

    # NULL을 sentinel 값으로 치환하는 functional unique index
    op.execute("""
        CREATE UNIQUE INDEX uq_sale_events_dedup
        ON sale_events (
            product_id,
            platform_id,
            COALESCE(start_date, '1900-01-01'::date),
            COALESCE(event_name, '')
        )
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sale_events_dedup")
