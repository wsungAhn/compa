"""Celery task for on-demand product collection."""
import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.scrapers.collector import (
    find_exact_for_sweep,
    get_platform,
    get_enabled_scrapers,
    group_events_by_product_name,
    persist_events_for_product,
)
from app.scrapers.collector import collect_on_demand
from app.scrapers.brands.shopify import BRAND_SCRAPERS
from app.tasks import celery

logger = logging.getLogger(__name__)


def collect_all_products() -> int:
    """Collect sale events for all products. Returns number of products refreshed."""
    return asyncio.run(_collect_all())


collect_all_products = celery.task(collect_all_products)


async def _collect_all() -> int:
    """브랜드 공홈 카탈로그를 훑어 기존 상품의 가격을 갱신한다."""
    enabled = get_enabled_scrapers()
    brand_names = [name for name in enabled if name in BRAND_SCRAPERS]

    if not brand_names:
        logger.error("brand catalog sweep disabled: no brand scrapers enabled")
        return 0

    async with AsyncSessionLocal() as db:
        matched_products = 0
        updated_products = 0
        skipped_groups = 0
        inserted_events = 0
        fail_count = 0

        for platform_name in brand_names:
            try:
                ScraperClass = BRAND_SCRAPERS[platform_name]
                scraper = ScraperClass()
                events = await scraper.scrape("")
                if not any(event.confidence > 0 for event in events):
                    fail_count += 1
                    logger.warning("brand %s scrape failed: sentinel or empty result", platform_name)
                    continue

                platform = await get_platform(db, platform_name)
                if platform is None:
                    fail_count += 1
                    logger.warning("brand %s missing platform row", platform_name)
                    continue

                for product_name, group in group_events_by_product_name(events).items():
                    product = await find_exact_for_sweep(db, product_name, ScraperClass.BRAND)
                    if product is None:
                        skipped_groups += 1
                        continue

                    matched_products += 1
                    inserted_here = await persist_events_for_product(db, product, platform, group)
                    if inserted_here > 0:
                        updated_products += 1
                    inserted_events += inserted_here
            except Exception as exc:
                await db.rollback()
                fail_count += 1
                logger.warning("brand %s failed: %s", platform_name, exc)
                continue

        logger.info(
            "brand catalog sweep: %d brands ok=%d fail=%d | products matched=%d updated=%d skipped=%d | events inserted=%d",
            len(brand_names),
            len(brand_names) - fail_count,
            fail_count,
            matched_products,
            updated_products,
            skipped_groups,
            inserted_events,
        )
        return updated_products


def run_collection_slow(query: str) -> int:
    """Celery task: full platform collection for a query. Returns product count."""
    return asyncio.run(_run_collection_slow(query))


run_collection_slow = celery.task(run_collection_slow)


async def _run_collection_slow(query: str) -> int:
    async with AsyncSessionLocal() as db:
        products = await collect_on_demand(db, query, force=True)
        return len(products)
