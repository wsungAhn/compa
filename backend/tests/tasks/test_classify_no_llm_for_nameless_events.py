"""분류 큐가 Claude를 부르는 조건 검증.

2026-08-09 실측: 미분류 1,573건이 전부 수집기가 찍은 기계 문자열("<브랜드> 공홈
현재가/할인", reason 전부 NULL)이었는데 10분마다 Claude를 16회씩 불렀다. 호출이
실패하면 event_type이 NULL로 남아 같은 행을 영원히 다시 부르는 구조였다.

여기서 막는 회귀는 둘:
  (1) 할인가 없는 "현재가" 스냅샷이 큐에 들어오는 것
  (2) reason 없는 이벤트에 Claude를 부르는 것
둘 중 하나라도 풀리면 EventClassifier 생성에서 터진다.
"""
import uuid

import pytest
from sqlalchemy import delete, select

import app.tasks.classify as classify_mod
from app.core.database import AsyncSessionLocal, engine
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent

pytestmark = pytest.mark.asyncio

_MARKER = "pytest-classify-guard"


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    async with AsyncSessionLocal() as db:
        await db.execute(delete(SaleEvent).where(SaleEvent.event_name.like(f"{_MARKER}%")))
        await db.commit()
    await engine.dispose()


async def _seed() -> tuple[uuid.UUID, uuid.UUID]:
    """현재가 1건 + 할인 1건을 심는다. 둘 다 reason 없음 — 실측 데이터와 동일."""
    async with AsyncSessionLocal() as db:
        product = (await db.execute(select(Product).limit(1))).scalar_one()
        platform = (await db.execute(select(Platform).limit(1))).scalar_one()
        snapshot = SaleEvent(
            product_id=product.id,
            platform_id=platform.id,
            event_name=f"{_MARKER} 공홈 현재가",
            original_price=None,
            sale_price=42.0,
        )
        discount = SaleEvent(
            product_id=product.id,
            platform_id=platform.id,
            event_name=f"{_MARKER} 공홈 할인",
            original_price=60.0,
            sale_price=42.0,
        )
        db.add_all([snapshot, discount])
        await db.commit()
        return snapshot.id, discount.id


async def test_machine_named_events_never_reach_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot_id, discount_id = await _seed()

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("reason 없는 이벤트에 Claude를 불렀다")

    # 태스크가 except Exception으로 삼키므로 BaseException으로 뚫고 나온다.
    monkeypatch.setattr(classify_mod, "EventClassifier", _boom)
    monkeypatch.setattr(classify_mod.settings, "anthropic_api_key", "sk-test")

    await classify_mod._classify_pending(limit=500)

    async with AsyncSessionLocal() as db:
        snapshot = (await db.execute(select(SaleEvent).where(SaleEvent.id == snapshot_id))).scalar_one()
        discount = (await db.execute(select(SaleEvent).where(SaleEvent.id == discount_id))).scalar_one()

    # 현재가는 세일이 아니므로 분류 대상 자체가 아니다.
    assert snapshot.event_type is None
    # 할인은 규칙으로 결론내고 사람 검토로 넘긴다.
    assert discount.event_type == "surprise"
    assert discount.needs_review is True
