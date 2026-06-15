"""Celery task for extracting social post events."""
import asyncio

from app.ai.pipeline import process_social_posts
from app.core.database import AsyncSessionLocal
from app.tasks import celery


def extract_social_posts(limit: int = 20) -> int:
    """Extract social posts and create SaleEvents. Returns count of events created."""
    return asyncio.run(_extract_social_posts(limit))


extract_social_posts = celery.task(extract_social_posts)


async def _extract_social_posts(limit: int = 20) -> int:
    """Process social posts and create SaleEvents."""
    async with AsyncSessionLocal() as db:
        return await process_social_posts(db, limit)
