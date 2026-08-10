"""Celery task for classifying pending sale events."""
import asyncio

from sqlalchemy import select

from app.ai.classifier import EventClassifier, classify_rule_based
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.sale_event import SaleEvent
from app.tasks import celery


def classify_pending(limit: int = 50) -> int:
    """Classify pending sale events. Returns number classified."""
    return asyncio.run(_classify_pending(limit))


classify_pending = celery.task(classify_pending)


async def _classify_pending(limit: int = 50) -> int:
    """Classify pending SaleEvents where event_type is NULL."""
    async with AsyncSessionLocal() as db:
        # Select unclassified events
        result = await db.execute(
            select(SaleEvent)
            .where(
                SaleEvent.event_type.is_(None),
                SaleEvent.deleted_at.is_(None),
                SaleEvent.event_name.isnot(None),
                # 할인가가 없는 "<브랜드> 공홈 현재가" 스냅샷은 세일이 아니라 시세 관측이다.
                # 분류할 대상이 아닌데 큐 앞자리를 영구 점유하며 매 실행 Claude를 불렀다.
                SaleEvent.original_price.isnot(None),
            )
            .limit(limit)
        )
        events: list[SaleEvent] = list(result.scalars().all())

        count = 0
        for event in events:
            try:
                # Try rule-based classification first
                rule_result = classify_rule_based(event.event_name, event.reason, event.start_date)
                if rule_result:
                    event.event_type = rule_result.event_type
                    event.needs_review = False
                    count += 1
                    continue

                # reason이 없으면 프롬프트에 실을 정보가 event_name 하나뿐이고,
                # 그 이름은 수집기가 찍은 "<브랜드> 공홈 할인" 같은 기계 문자열이다.
                # 알려진 정기행사 키워드에 안 걸린 이상 상시/돌발 할인으로 두고
                # 사람 검토 대상으로 넘긴다 — Claude를 불러도 같은 문자열만 되읽는다.
                if not event.reason:
                    event.event_type = "surprise"
                    event.needs_review = True
                    count += 1
                    continue

                # If rule-based fails and API key is set, use Claude
                if settings.anthropic_api_key:
                    # Fetch past events for this product
                    past_result = await db.execute(
                        select(SaleEvent)
                        .where(
                            SaleEvent.product_id == event.product_id,
                            SaleEvent.event_type.isnot(None),
                            SaleEvent.deleted_at.is_(None),
                        )
                        .order_by(SaleEvent.start_date.desc())
                        .limit(10)
                    )
                    past_events = list(past_result.scalars().all())

                    # Convert to dicts for classifier
                    past_dicts: list[dict[str, object]] = [
                        {
                            "event_name": e.event_name,
                            "start_date": e.start_date,
                            "event_type": e.event_type,
                        }
                        for e in past_events
                    ]

                    classifier = EventClassifier()
                    classification = await classifier.classify(
                        event.event_name,
                        event.reason,
                        event.start_date,
                        past_dicts,
                    )
                    event.event_type = classification.event_type
                    if classification.confidence < 0.7:
                        event.needs_review = True
                    count += 1

            except Exception:
                # Swallow exceptions per spec, don't propagate
                continue

        # Commit once at the end
        await db.commit()

        return count
