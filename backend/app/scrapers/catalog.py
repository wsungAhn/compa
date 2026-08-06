"""제품 카탈로그 시딩 — 브랜드 공홈(Shopify products.json)에서 제품명 수집.

이전에는 네이버 쇼핑 검색 API로 브랜드명을 검색해 시딩했다. 그 API가 2026년
7월 종료되면서(docs/scrapers.md) 시딩 자체가 불가능해졌고, 대체 소스인 브랜드
공홈 레지스트리가 같은 일을 더 잘한다 — 검색어 추측 없이 브랜드 카탈로그 전체를
받고, 가격·정가까지 같이 온다.
"""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.scrapers.brands.shopify import BRAND_SCRAPERS

logger = logging.getLogger(__name__)

# 브랜드당 시딩할 최대 제품 수 (카탈로그가 큰 브랜드가 DB를 독식하지 않도록)
MAX_PER_BRAND = 100


async def seed_catalog(db: AsyncSession, brands: list[str] | None = None) -> int:
    """브랜드 공홈 카탈로그를 products 테이블에 시딩.

    Args:
        db: DB 세션
        brands: 플랫폼명 목록(예: ["Tatcha 공홈"]). None이면 레지스트리 전체.

    Returns:
        삽입된 신규 제품 수
    """
    targets = (
        {name: BRAND_SCRAPERS[name] for name in brands if name in BRAND_SCRAPERS}
        if brands is not None
        else dict(BRAND_SCRAPERS)
    )
    seeded = 0

    for platform_name, scraper_cls in targets.items():
        try:
            # 빈 쿼리 = 필터 없이 카탈로그 전체
            events = await scraper_cls().scrape("")
            usable = [e for e in events if e.confidence > 0][:MAX_PER_BRAND]
            for event in usable:
                name = event.product_name.strip()
                if not name:
                    continue
                existing = await db.execute(
                    select(Product).where(
                        Product.name_en == name,
                        Product.deleted_at.is_(None),
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                db.add(Product(name_en=name, brand=event.brand))
                seeded += 1
            await db.commit()
            logger.info("Seeded '%s': %d items", platform_name, len(usable))
        except Exception as exc:
            logger.warning("Failed to seed '%s': %s", platform_name, exc)
            await db.rollback()
        await asyncio.sleep(0.5)

    logger.info("Catalog seed complete: %d new products", seeded)
    return seeded


async def seed_catalog_if_empty(db: AsyncSession) -> None:
    """products 테이블이 비어있을 때만 카탈로그 시딩 실행.

    이미 사용자가 수집한 제품이 있으면 완전히 스킵.
    """
    result = await db.execute(select(Product).limit(1))
    if result.scalar_one_or_none() is None:
        logger.info("Products table is empty — starting catalog seed...")
        await seed_catalog(db)
