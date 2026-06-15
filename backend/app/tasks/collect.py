"""Celery task for on-demand product collection."""
import asyncio

from sqlalchemy import distinct, select

from app.core.database import AsyncSessionLocal
from app.models.product import Product
from app.scrapers.collector import collect_on_demand
from app.tasks import celery


def collect_all_products() -> int:
    """Collect sale events for all products. Returns number of products refreshed."""
    return asyncio.run(_collect_all())


collect_all_products = celery.task(collect_all_products)


async def _collect_all() -> int:
    """Fetch all distinct product names and collect events for each."""
    async with AsyncSessionLocal() as db:
        # Select all distinct, non-deleted product names
        result = await db.execute(
            select(distinct(Product.name_kr)).where(Product.deleted_at.is_(None), Product.name_kr.isnot(None))
        )
        names = [n for n in result.scalars().all() if n is not None]

        count = 0
        for name in names:
            try:
                await collect_on_demand(db, name, force=True)
                count += 1
            except Exception:
                # Continue on failure, don't propagate exceptions
                continue

        return count


def run_collection_slow(query: str) -> int:
    """Celery task: full platform collection for a query. Returns product count."""
    return asyncio.run(_run_collection_slow(query))


run_collection_slow = celery.task(run_collection_slow)


async def _run_collection_slow(query: str) -> int:
    async with AsyncSessionLocal() as db:
        products = await collect_on_demand(db, query, force=True)
        return len(products)
