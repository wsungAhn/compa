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
