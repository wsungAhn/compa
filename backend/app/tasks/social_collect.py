"""Celery task for social media post collection."""
import asyncio

from sqlalchemy import distinct, select

from app.core.database import AsyncSessionLocal
from app.models.product import Product
from app.social.collector import collect_social_posts
from app.tasks import celery


def collect_social_for_products() -> int:
    """Collect social posts for all products. Returns number of products processed."""
    return asyncio.run(_collect_all())


collect_social_for_products = celery.task(collect_social_for_products)


async def _collect_all() -> int:
    """Fetch all distinct product names and collect social posts for each."""
    async with AsyncSessionLocal() as db:
        # Select all distinct, non-deleted product names in Korean
        result = await db.execute(
            select(distinct(Product.name_kr)).where(Product.deleted_at.is_(None), Product.name_kr.isnot(None))
        )
        names = [n for n in result.scalars().all() if n is not None]

        count = 0
        for name in names:
            try:
                await collect_social_posts(db, name)
                count += 1
            except Exception:
                # Continue on failure, don't propagate exceptions
                continue

        return count
