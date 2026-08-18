"""Celery task for low-risk database hygiene cleanup."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.platform_product_id import PlatformProductId
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.tasks import celery

logger = logging.getLogger(__name__)

EMPTY_PRODUCT_GRACE_HOURS = 24


def cleanup_empty_orphan_products() -> int:
    """Soft-delete products older than 24h that have never had sale events."""
    return asyncio.run(_cleanup_empty_orphan_products())


async def _cleanup_empty_orphan_products() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=EMPTY_PRODUCT_GRACE_HOURS)
    async with AsyncSessionLocal() as db:
        deleted = await _soft_delete_empty_orphan_products(db, cutoff)
        await db.commit()
    if deleted:
        logger.info("cleanup: soft-deleted %d empty orphan products", deleted)
    return deleted


async def _soft_delete_empty_orphan_products(db: AsyncSession, cutoff: datetime) -> int:
    orphan_ids = (
        select(Product.id)
        .where(
            Product.deleted_at.is_(None),
            Product.created_at < cutoff,
            ~exists(select(SaleEvent.id).where(SaleEvent.product_id == Product.id)),
        )
        .subquery()
    )
    orphan_id_select = select(orphan_ids.c.id)

    await db.execute(
        delete(PlatformProductId).where(PlatformProductId.product_id.in_(orphan_id_select))
    )
    result = await db.execute(
        update(Product)
        .where(Product.id.in_(orphan_id_select))
        .values(deleted_at=datetime.now(timezone.utc))
    )
    return int(result.rowcount or 0)


cleanup_empty_orphan_products = celery.task(cleanup_empty_orphan_products)
