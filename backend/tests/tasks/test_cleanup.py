"""Tests for periodic database hygiene cleanup tasks."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.models.platform import Platform
from app.models.platform_product_id import PlatformProductId
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.tasks.cleanup import _soft_delete_empty_orphan_products


async def _probe_live_pg_query() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(Product).limit(1))
            await db.commit()
    finally:
        await engine.dispose()


def _live_pg_skip_reason() -> str | None:
    try:
        asyncio.run(_probe_live_pg_query())
    except (OSError, SQLAlchemyError) as exc:
        return f"requires live PG: {type(exc).__name__}: {exc}"
    return None


LIVE_PG_SKIP_REASON = _live_pg_skip_reason()
LIVE_PG_UNAVAILABLE = LIVE_PG_SKIP_REASON is not None
LIVE_PG_MARK_REASON = LIVE_PG_SKIP_REASON or "requires live PG"


@pytest.fixture(autouse=True)
async def _dispose_engine() -> None:
    yield
    await engine.dispose()


@pytest.mark.skipif(LIVE_PG_UNAVAILABLE, reason=LIVE_PG_MARK_REASON)
@pytest.mark.asyncio
async def test_cleanup_empty_orphans_respects_age_and_sale_event_guards() -> None:
    marker = f"cleanup-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    old_cutoff = now - timedelta(hours=24)
    async with AsyncSessionLocal() as db:
        platform = Platform(name=marker, country="US")
        old_empty = Product(name_en=f"{marker}-old-empty", created_at=now - timedelta(hours=25))
        recent_empty = Product(name_en=f"{marker}-recent-empty", created_at=now - timedelta(hours=23))
        old_with_event = Product(name_en=f"{marker}-old-with-event", created_at=now - timedelta(hours=25))
        db.add_all([platform, old_empty, recent_empty, old_with_event])
        await db.flush()
        platform_id = platform.id
        old_empty_id = old_empty.id
        recent_empty_id = recent_empty.id
        old_with_event_id = old_with_event.id
        db.add_all(
            [
                PlatformProductId(
                    product_id=old_empty_id,
                    platform_id=platform_id,
                    external_id=f"{marker}-old-empty",
                    id_type="variant_id",
                ),
                SaleEvent(product_id=old_with_event_id, platform_id=platform_id),
            ]
        )
        await db.commit()

        deleted = await _soft_delete_empty_orphan_products(db, old_cutoff)
        await db.commit()
        db.expire_all()

        assert deleted >= 1
        assert await _deleted_at(db, old_empty_id) is not None
        assert await _deleted_at(db, recent_empty_id) is None
        assert await _deleted_at(db, old_with_event_id) is None
        mapping = (
            await db.execute(
                select(PlatformProductId).where(PlatformProductId.external_id == f"{marker}-old-empty")
            )
        ).scalar_one_or_none()
        assert mapping is None

        await db.execute(delete(SaleEvent).where(SaleEvent.platform_id == platform_id))
        await db.execute(delete(PlatformProductId).where(PlatformProductId.platform_id == platform_id))
        await db.execute(
            delete(Product).where(
                Product.id.in_([old_empty_id, recent_empty_id, old_with_event_id])
            )
        )
        await db.execute(delete(Platform).where(Platform.id == platform_id))
        await db.commit()


async def _deleted_at(db: AsyncSession, product_id: uuid.UUID) -> datetime | None:
    return (
        await db.execute(select(Product.deleted_at).where(Product.id == product_id))
    ).scalar_one()
