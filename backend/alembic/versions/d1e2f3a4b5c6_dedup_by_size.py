"""include size_ml in sale_events dedup key

용량마다 가격이 다른데 유니크 키에 용량이 없어, 같은 제품·플랫폼·같은 날의
variant들이 전부 충돌해 on_conflict_do_nothing으로 조용히 버려졌다
(2026-08-06 실측: PITERA 에센스 4개 용량 중 1건만 저장).

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = (
    "product_id, platform_id, COALESCE(start_date, '1900-01-01'::date), "
    "COALESCE(event_name, ''::character varying)"
)
_NEW = _OLD + ", COALESCE(size_ml, -1)"


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sale_events_dedup")
    op.execute(
        f"CREATE UNIQUE INDEX uq_sale_events_dedup ON sale_events "
        f"USING btree ({_NEW}) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_sale_events_dedup")
    op.execute(
        f"CREATE UNIQUE INDEX uq_sale_events_dedup ON sale_events "
        f"USING btree ({_OLD}) WHERE deleted_at IS NULL"
    )
