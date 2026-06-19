"""제품 할인 이벤트 수집기 — 다국가 스크래퍼 통합 실행."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings

from deep_translator import GoogleTranslator
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classifier import classify_rule_based
from app.ai.matcher import get_or_create_product
from app.core.database import AsyncSessionLocal
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers.base import BaseScraper, ScrapedEvent
from app.scrapers.brands.amoremall import AmoremallScraper
from app.scrapers.brands.chantecaille_kr import ChantecailleKRScraper
from app.scrapers.brands.lamer_kr import LaMerKRScraper
from app.scrapers.brands.laprairie import LaPrairieScraper
from app.scrapers.brands.skii import SKIIScraper
from app.scrapers.brands.tatcha import TatchaScraper
from app.scrapers.cn.tmall import TmallScraper
from app.scrapers.cn.xiaohongshu import XiaohongshuScraper
from app.scrapers.jp.cosme import CosmeScraper
from app.scrapers.jp.rakuten import RakutenScraper
from app.scrapers.kr.coupang import CoupangScraper
from app.scrapers.kr.naver_shop import NaverShopScraper
from app.scrapers.kr.oliveyoung import OliveYoungScraper
from app.scrapers.us.amazon import AmazonScraper
from app.scrapers.us.sephora import SephoraScraper
from app.scrapers.us.shiseido import ShiseidoScraper
from app.scrapers.us.ulta import UltaScraper

# (ScraperClass, search_lang) — country-aware translation
SCRAPERS: dict[str, tuple[type[BaseScraper], str]] = {
    "올리브영":  (OliveYoungScraper, "ko"),
    "아모레몰":  (AmoremallScraper,  "ko"),
    "네이버쇼핑": (NaverShopScraper, "ko"),
    "쿠팡":      (CoupangScraper,   "ko"),
    "Sephora":   (SephoraScraper,   "en"),
    "Ulta":      (UltaScraper,      "en"),
    "Amazon US": (AmazonScraper,    "en"),
    "SK-II Official":          (SKIIScraper,           "en"),
    "Shiseido Official":       (ShiseidoScraper,       "en"),
    "La Mer Official KR":      (LaMerKRScraper,        "ko"),
    "Chantecaille Official KR":(ChantecailleKRScraper, "ko"),
    "La Prairie Official":     (LaPrairieScraper,      "ko"),
    "Tatcha Official":         (TatchaScraper,         "en"),
    "Rakuten":   (RakutenScraper,   "ja"),
    "@cosme":    (CosmeScraper,     "ja"),
    "Tmall":     (TmallScraper,     "zh"),
    "小红书":    (XiaohongshuScraper,"zh"),
}

def get_enabled_scrapers() -> dict[str, tuple[type[BaseScraper], str]]:
    """settings.enabled_scrapers 기반 활성 스크래퍼 반환.

    "all" → SCRAPERS 전체, 아니면 이름 정확 일치 부분집합.
    미존재 이름은 무시 (예외 금지).
    """
    raw = settings.enabled_scrapers.strip()
    if raw.lower() == "all":
        return dict(SCRAPERS)
    names = [n.strip() for n in raw.split(",") if n.strip()]
    return {name: SCRAPERS[name] for name in names if name in SCRAPERS}


CACHE_TTL_HOURS = 24
_BUNDLE_KEYWORDS = {"세트", "set", "kit", "duo", "bundle", "기획", "스페셜"}

# 403/503 차단으로 수집 불가한 플랫폼
SKIP_SCRAPERS: set[str] = set()

# 빠른 경로: REST API만 사용하는 플랫폼
FAST_SCRAPERS: set[str] = {"네이버쇼핑"}

# Browser 스크래퍼 목록 (semaphore 적용)
_BROWSER_SCRAPERS: set[str] = {
    "올리브영", "아모레몰", "Sephora", "SK-II Official", "Shiseido Official",
    "La Mer Official KR", "Chantecaille Official KR", "La Prairie Official", "Tatcha Official",
}

# 번역 결과 인메모리 캐시
_translate_cache: dict[tuple[str, str], str] = {}

# 스크래퍼 인스턴스 캐시 (rate limiting 유지)
_scraper_instances: dict[str, BaseScraper] = {}

# Browser 동시성 제한
_BROWSER_SEMAPHORE = asyncio.Semaphore(4)

_logger = logging.getLogger(__name__)


def _is_bundle(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _BUNDLE_KEYWORDS)


def _translate(query: str, target_lang: str) -> str:
    """동기 번역 함수 — asyncio.to_thread로 실행해야 함."""
    if target_lang == "ko":
        return query
    key = (query, target_lang)
    if key not in _translate_cache:
        try:
            _translate_cache[key] = GoogleTranslator(source="auto", target=target_lang).translate(query)
        except Exception:
            _translate_cache[key] = query
    return _translate_cache[key]


def _classify_event_type(s: ScrapedEvent) -> str | None:
    result = classify_rule_based(s.event_name, s.reason, s.start_date)
    if result:
        return result.event_type
    return None


def _event_signature(s: ScrapedEvent) -> tuple[str | None, float | None, float | None, object]:
    return (s.event_name, s.sale_price, s.original_price, s.start_date)


async def _is_duplicate(
    db: AsyncSession,
    product: Product,
    platform: Platform,
    s: ScrapedEvent,
) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    event_name, sale_price, original_price, start_date = _event_signature(s)

    conditions = [
        SaleEvent.product_id == product.id,
        SaleEvent.platform_id == platform.id,
        SaleEvent.event_name == event_name,
        SaleEvent.start_date == start_date,
        SaleEvent.deleted_at.is_(None),
        SaleEvent.created_at >= cutoff,
    ]

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


async def _fresh_platforms(db: AsyncSession, product: Product) -> set[str]:
    """24h TTL 내에 수집된 플랫폼 이름 집합 반환."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    result = await db.execute(
        select(Platform.name)
        .join(SaleEvent, SaleEvent.platform_id == Platform.id)
        .where(SaleEvent.product_id == product.id, SaleEvent.created_at >= cutoff)
        .distinct()
    )
    return {row[0] for row in result.all()}


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

        if await _is_duplicate(db, product, platform, s):
            continue

        event_type = _classify_event_type(s)
        stmt = pg_insert(SaleEvent).values(
            id=uuid.uuid4(),
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
            scraped_name=s.product_name,
            is_bundle=_is_bundle(s.product_name),
            raw_text=s.raw_text,
        ).on_conflict_do_nothing()
        await db.execute(stmt)
    await db.commit()


def _get_platform_country(platform_name: str) -> str:
    """플랫폼 이름에서 country 코드 추정."""
    lang = SCRAPERS.get(platform_name, (None, "ko"))[1]
    return {"ko": "KR", "en": "US", "ja": "JP", "zh": "CN"}.get(lang, "KR")


async def _collect_platform(
    product_id: uuid.UUID,
    platform_name: str,
    query: str,
    platform_country: str,
    force: bool = False,
) -> None:
    """단일 플랫폼 수집 (asyncio.gather 병렬 실행용)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        product = result.scalar_one_or_none()
        if not product:
            return

        platform = await _get_platform(db, platform_name)
        if not platform:
            return

        if not force:
            fresh = await _fresh_platforms(db, product)
            if platform_name in fresh:
                return

        ScraperClass, target_lang = SCRAPERS[platform_name]
        translated_query = await asyncio.to_thread(_translate, query, target_lang)

        if platform_name not in _scraper_instances:
            _scraper_instances[platform_name] = ScraperClass()
        scraper = _scraper_instances[platform_name]

        try:
            if platform_name in _BROWSER_SCRAPERS:
                async with _BROWSER_SEMAPHORE:
                    scraped_events = await scraper.scrape(translated_query)
            else:
                scraped_events = await scraper.scrape(translated_query)

            by_product: dict[str, list[ScrapedEvent]] = {}
            for s in scraped_events:
                if s.confidence > 0:
                    by_product.setdefault(s.product_name, []).append(s)

            for product_name, events in by_product.items():
                brand = events[0].brand if events else None
                prod = await get_or_create_product(db, product_name, brand, platform_country)
                await _save_events(db, prod, platform, events)

        except Exception as exc:
            _logger.warning("Platform %s scrape failed: %s", platform_name, exc)


async def collect_fast(db: AsyncSession, query: str) -> list[Product]:
    """빠른 경로: 활성 스크래퍼 중 FAST_SCRAPERS만 실행 (~1-2s, Naver REST API)."""
    # Get or create a product for this query using KR as default
    product = await get_or_create_product(db, query, None, "KR")
    await db.commit()
    await db.refresh(product)

    enabled = get_enabled_scrapers()
    stale = [
        name for name in FAST_SCRAPERS
        if name not in SKIP_SCRAPERS and name in enabled
    ]
    if stale:
        platform_country = _get_platform_country(stale[0])
        await asyncio.gather(*[
            _collect_platform(product.id, name, query, platform_country)
            for name in stale
        ])
    return [product]


async def collect_on_demand(db: AsyncSession, query: str, force: bool = False) -> list[Product]:
    """쿼리에 해당하는 제품을 모든 플랫폼에서 수집해 저장.

    force=True: 제품 캐시 및 플랫폼별 24h freshness 체크 모두 건너뜀.
    """
    # 기존 제품 확인
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

    # Ensure product exists for this query
    product = await get_or_create_product(db, query, None, "KR")
    await db.commit()
    await db.refresh(product)

    enabled = get_enabled_scrapers()
    stale_platforms = [
        name for name in enabled
        if name not in SKIP_SCRAPERS
    ]

    await asyncio.gather(*[
        _collect_platform(product.id, name, query, _get_platform_country(name), force=force)
        for name in stale_platforms
    ])

    return [product] if not existing else existing
