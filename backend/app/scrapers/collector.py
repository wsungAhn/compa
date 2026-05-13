from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers.base import ScrapedEvent
from app.scrapers.jp.rakuten import RakutenScraper
from app.scrapers.kr.coupang import CoupangScraper
from app.scrapers.kr.naver_shop import NaverShopScraper
from app.scrapers.kr.oliveyoung import OliveYoungScraper
from app.scrapers.us.amazon import AmazonScraper
from app.scrapers.us.sephora import SephoraScraper

SCRAPERS = {
    "네이버쇼핑": NaverShopScraper,
    "쿠팡": CoupangScraper,
    "올리브영": OliveYoungScraper,
    "Sephora": SephoraScraper,
    "Amazon US": AmazonScraper,
    "Rakuten": RakutenScraper,
}

CACHE_TTL_HOURS = 24


async def _is_fresh(db: AsyncSession, product: Product) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    result = await db.execute(
        select(SaleEvent)
        .where(SaleEvent.product_id == product.id, SaleEvent.created_at >= cutoff)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _get_or_create_product(db: AsyncSession, name: str, brand: str | None) -> Product:
    result = await db.execute(
        select(Product).where(Product.name_kr == name, Product.deleted_at.is_(None))
    )
    product = result.scalar_one_or_none()
    if not product:
        product = Product(name_kr=name, name_en=name, brand=brand)
        db.add(product)
        await db.flush()
    return product


async def _get_platform(db: AsyncSession, name: str) -> Platform | None:
    result = await db.execute(select(Platform).where(Platform.name == name))
    return result.scalar_one_or_none()


async def _save_events(
    db: AsyncSession,
    product: Product,
    platform: Platform,
    scraped: list[ScrapedEvent],
) -> None:
    for s in scraped:
        if s.confidence == 0.0:
            continue
        event = SaleEvent(
            product_id=product.id,
            platform_id=platform.id,
            event_name=s.event_name,
            start_date=s.start_date,
            end_date=s.end_date,
            original_price=s.original_price,
            sale_price=s.sale_price,
            discount_rate=s.discount_rate,
            currency=s.currency or "KRW",
            reason=s.reason,
            source_url=s.source_url,
            confidence=s.confidence,
            needs_review=s.confidence < 0.7,
            raw_text=s.raw_text,
        )
        db.add(event)
    await db.commit()


async def collect_on_demand(db: AsyncSession, query: str) -> list[Product]:
    """쿼리에 해당하는 제품을 스크래핑해서 DB에 저장 후 Product 목록 반환."""
    # 기존 제품 확인
    result = await db.execute(
        select(Product).where(
            Product.name_kr.ilike(f"%{query}%"),
            Product.deleted_at.is_(None),
        )
    )
    existing = list(result.scalars().all())

    # 캐시가 유효하면 바로 반환
    if existing and await _is_fresh(db, existing[0]):
        return existing

    # 스크래핑 실행
    new_products: list[Product] = []
    for platform_name, ScraperClass in SCRAPERS.items():
        platform = await _get_platform(db, platform_name)
        if not platform:
            continue

        scraper = ScraperClass()
        try:
            scraped_events = await scraper.scrape(query)
        except Exception:
            continue

        # 제품명별로 그룹핑
        by_product: dict[str, list[ScrapedEvent]] = {}
        for s in scraped_events:
            if s.confidence > 0:
                by_product.setdefault(s.product_name, []).append(s)

        for product_name, events in by_product.items():
            brand = events[0].brand if events else None
            product = await _get_or_create_product(db, product_name, brand)
            await _save_events(db, product, platform, events)
            if product not in new_products:
                new_products.append(product)

    return new_products if new_products else existing
