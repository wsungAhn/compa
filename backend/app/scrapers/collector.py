from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classifier import classify_rule_based
from app.ai.matcher import get_or_create_product
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers.base import BaseScraper, ScrapedEvent
from app.scrapers.jp.cosme import CosmeScraper
from app.scrapers.jp.rakuten import RakutenScraper
from app.scrapers.kr.coupang import CoupangScraper
from app.scrapers.kr.naver_shop import NaverShopScraper
from app.scrapers.kr.oliveyoung import OliveYoungScraper
from app.scrapers.us.amazon import AmazonScraper
from app.scrapers.us.sephora import SephoraScraper
from app.scrapers.us.ulta import UltaScraper

SCRAPERS: dict[str, Callable[[], BaseScraper]] = {
    "네이버쇼핑": NaverShopScraper,
    "쿠팡": CoupangScraper,
    "올리브영": OliveYoungScraper,
    "Sephora": SephoraScraper,
    "Ulta": UltaScraper,
    "Amazon US": AmazonScraper,
    "@cosme": CosmeScraper,
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




async def _get_platform(db: AsyncSession, name: str) -> Platform | None:
    result = await db.execute(select(Platform).where(Platform.name == name))
    return result.scalar_one_or_none()


def _classify_event_type(s: ScrapedEvent) -> str | None:
    """이벤트명과 사유로 빠른 분류를 시도하고, 결과가 있으면 event_type 반환."""
    result = classify_rule_based(s.event_name, s.reason, s.start_date)
    if result:
        return result.event_type
    return None


def _event_signature(s: ScrapedEvent) -> tuple[str | None, float | None, float | None, object]:
    """
    Extract event signature for deduplication.

    Returns tuple of (event_name, sale_price, original_price, start_date).
    """
    return (s.event_name, s.sale_price, s.original_price, s.start_date)


async def _is_duplicate(
    db: AsyncSession,
    product: Product,
    platform: Platform,
    s: ScrapedEvent,
) -> bool:
    """
    Check if a "same" event already exists within the last 7 days.

    Same event: same product_id, platform_id, event_name, sale_price, original_price, start_date,
    with deleted_at IS NULL, created within last 7 days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    event_name, sale_price, original_price, start_date = _event_signature(s)

    # Build where clause with conditional None handling
    conditions = [
        SaleEvent.product_id == product.id,
        SaleEvent.platform_id == platform.id,
        SaleEvent.event_name == event_name,
        SaleEvent.start_date == start_date,
        SaleEvent.deleted_at.is_(None),
        SaleEvent.created_at >= cutoff,
    ]

    # Handle nullable price fields: compare with SQL equality (SQLAlchemy handles NUMERIC casting)
    if sale_price is None:
        conditions.append(SaleEvent.sale_price.is_(None))
    else:
        conditions.append(SaleEvent.sale_price == sale_price)

    if original_price is None:
        conditions.append(SaleEvent.original_price.is_(None))
    else:
        conditions.append(SaleEvent.original_price == original_price)

    result = await db.execute(select(SaleEvent).where(*conditions).limit(1))
    return result.scalar_one_or_none() is not None


async def _save_events(
    db: AsyncSession,
    product: Product,
    platform: Platform,
    scraped: list[ScrapedEvent],
) -> None:
    for s in scraped:
        if s.confidence == 0.0:
            continue

        # Check for duplicate before inserting
        if await _is_duplicate(db, product, platform, s):
            continue

        event_type = _classify_event_type(s)
        event = SaleEvent(
            product_id=product.id,
            platform_id=platform.id,
            event_name=s.event_name,
            event_type=event_type,
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


async def collect_on_demand(db: AsyncSession, query: str, force: bool = False) -> list[Product]:
    """쿼리에 해당하는 제품을 스크래핑해서 DB에 저장 후 Product 목록 반환."""
    # 기존 제품 확인 — 4개국 name 컬럼 모두 검색
    result = await db.execute(
        select(Product).where(
            or_(
                Product.name_kr.ilike(f"%{query}%"),
                Product.name_en.ilike(f"%{query}%"),
                Product.name_jp.ilike(f"%{query}%"),
                Product.name_cn.ilike(f"%{query}%"),
            ),
            Product.deleted_at.is_(None),
        )
    )
    existing = list(result.scalars().all())

    # 캐시가 유효하면 바로 반환 (force=True일 때는 스킵)
    if not force and existing and await _is_fresh(db, existing[0]):
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
            product = await get_or_create_product(db, product_name, brand, platform.country)
            await _save_events(db, product, platform, events)
            if product not in new_products:
                new_products.append(product)

    return new_products if new_products else existing
