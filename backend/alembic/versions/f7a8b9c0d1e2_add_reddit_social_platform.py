"""add reddit to social_platform enum

Reddit 딜 신호를 social_posts에 저장하기 위해 enum 값을 추가한다.
설계: docs/design-reddit-deal-signals-2026-08-06.md

Revision ID: f7a8b9c0d1e2
Revises: e6a7b8c9d0f1
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6a7b8c9d0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres는 enum 값 추가만 지원한다(제거 불가).
    op.execute("ALTER TYPE social_platform ADD VALUE IF NOT EXISTS 'reddit'")


def downgrade() -> None:
    # enum 값 제거는 Postgres가 지원하지 않는다. 되돌리려면 타입을 재생성해야 하는데,
    # 그 사이 'reddit' 행이 있으면 실패한다 — 48시간 정리 태스크가 비우고 나서만
    # 가능하므로 자동 downgrade는 제공하지 않는다.
    op.execute("DELETE FROM social_posts WHERE platform = 'reddit'")
