"""Celery task for catalog seeding."""
import asyncio

from app.core.database import AsyncSessionLocal
from app.scrapers.catalog import seed_catalog
from app.tasks import celery


def seed_catalog_task() -> int:
    """Celery task: seed product catalog from Naver API. Returns new product count."""
    return asyncio.run(_seed_catalog())

seed_catalog_task = celery.task(seed_catalog_task)


async def _seed_catalog() -> int:
    async with AsyncSessionLocal() as db:
        return await seed_catalog(db)
