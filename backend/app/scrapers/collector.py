import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from deep_translator import GoogleTranslator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers.base import BaseScraper, ScrapedEvent
from app.scrapers.brands.chantecaille_kr import ChantecailleKRScraper
from app.scrapers.brands.lamer_kr import LaMerKRScraper
from app.scrapers.brands.laprairie import LaPrairieScraper
from app.scrapers.brands.skii import SKIIScraper
from app.scrapers.brands.tatcha import TatchaScraper
from app.scrapers.cn.tmall import TmallScraper
from app.scrapers.cn.xiaohongshu import XiaohongshuScraper
from app.scrapers.jp.cosme import CosmeScraper
from app.scrapers.jp.rakuten import RakutenScraper
from app.scrapers.kr.naver_shop import NaverShopScraper
from app.scrapers.kr.oliveyoung import OliveYoungScraper
from app.scrapers.us.amazon_us import AmazonUSScraper
from app.scrapers.us.sephora import SephoraScraper
from app.scrapers.us.shiseido import ShiseidoScraper
from app.scrapers.us.ulta import UltaScraper

# (스크래퍼 클래스, 검색 언어)
SCRAPERS: dict[str, tuple[type, str]] = {
    "올리브영":  (OliveYoungScraper, "ko"),
    "네이버쇼핑": (NaverShopScraper,  "ko"),
    "Sephora":   (SephoraScraper,    "en"),
    "Ulta":      (UltaScraper,       "en"),
    "Amazon US": (AmazonUSScraper,   "en"),
    "SK-II Official": (SKIIScraper,  "en"),
    "Shiseido Official": (ShiseidoScraper, "en"),
    "La Mer Official KR": (LaMerKRScraper, "ko"),
    "Chantecaille Official KR": (ChantecailleKRScraper, "ko"),
    "La Prairie Official": (LaPrairieScraper, "ko"),
    "Tatcha Official": (TatchaScraper, "en"),
    "Rakuten":   (RakutenScraper,    "ja"),
    "@cosme":    (CosmeScraper,      "ja"),
    "Tmall":     (TmallScraper,      "zh"),
    "小红书":    (XiaohongshuScraper, "zh"),
}

CACHE_TTL_HOURS = 24
_BUNDLE_KEYWORDS = {"세트", "set", "kit", "duo", "bundle", "기획", "스페셜"}

# 403/503 차단으로 수집 불가한 플랫폼 — 공식 API 확보 전까지 스킵
SKIP_SCRAPERS: set[str] = {}  # firecrawl stealth로 전환 후 차단 재확인 필요시 추가

# 빠른 경로: REST API만 사용하는 플랫폼 (Playwright 불필요)
FAST_SCRAPERS: set[str] = {"네이버쇼핑"}

# 번역 결과 인메모리 캐시 {(text, target_lang): result}
_translate_cache: dict[tuple[str, str], str] = {}

# 스크래퍼 인스턴스 캐시 — rate limiting 유지
_scraper_instances: dict[str, BaseScraper] = {}

# Browser 동시성 제한 — Chrome 프로세스 수 제어
_BROWSER_SEMAPHORE = asyncio.Semaphore(4)


def _is_bundle(name: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in _BUNDLE_KEYWORDS)


def _translate(query: str, target_lang: str) -> str:
    if target_lang == "ko":
        return query
    key = (query, target_lang)
    if key not in _translate_cache:
        try:
            _translate_cache[key] = GoogleTranslator(source="auto", target=target_lang).translate(query)
        except Exception:
            _translate_cache[key] = query
    return _translate_cache[key]


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


async def _get_or_create_product(db: AsyncSession, query: str, brand: str | None) -> Product:
    """query를 canonical name_kr로 사용하는 단일 Product 행 반환."""
    result = await db.execute(
        select(Product).where(Product.name_kr == query, Product.deleted_at.is_(None))
    )
    product = result.scalar_one_or_none()
    if not product:
        product = Product(name_kr=query, name_en=query, brand=brand)
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
        stmt = pg_insert(SaleEvent).values(
            id=uuid.uuid4(),
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
            scraped_name=s.product_name,
            is_bundle=_is_bundle(s.product_name),
            raw_text=s.raw_text,
        ).on_conflict_do_nothing()
        await db.execute(stmt)
    await db.commit()


async def _collect_platform(
    product_id: uuid.UUID,
    platform_name: str,
    query: str,
) -> None:
    """단일 플랫폼 수집 (asyncio.gather 병렬 실행용)."""
    # 자체 세션 생성 — asyncio.gather 공유 세션 충돌 방지
    async with AsyncSessionLocal() as db:
        # product_id로 재fetch
        result = await db.execute(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        product = result.scalar_one_or_none()
        if not product:
            return

        ScraperClass, target_lang = SCRAPERS[platform_name]
        platform = await _get_platform(db, platform_name)
        if not platform:
            return
        translated_query = _translate(query, target_lang)

        # 스크래퍼 인스턴스 캐시 — rate limiting 유지
        if platform_name not in _scraper_instances:
            _scraper_instances[platform_name] = ScraperClass()
        scraper = _scraper_instances[platform_name]

        try:
            # Browser 동시성 제한
            async with _BROWSER_SEMAPHORE:
                scraped_events = await scraper.scrape(translated_query)
            valid = [s for s in scraped_events if s.confidence > 0]
            if valid:
                await _save_events(db, product, platform, valid)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Platform %s scrape failed: %s", platform_name, exc
            )


async def collect_fast(db: AsyncSession, query: str) -> list[Product]:
    """빠른 경로: FAST_SCRAPERS만 실행 (~1-2s, Naver REST API)."""
    product = await _get_or_create_product(db, query, brand=None)
    # 신규 product가 flush만 된 상태이면 다른 세션에서 조회 불가 → commit으로 가시성 확보
    await db.commit()
    await db.refresh(product)

    fresh = await _fresh_platforms(db, product)
    stale = [
        name for name in FAST_SCRAPERS
        if name not in fresh and name not in SKIP_SCRAPERS
    ]
    if stale:
        await asyncio.gather(*[
            _collect_platform(product.id, name, query)
            for name in stale
        ])
    return [product]


async def collect_on_demand(db: AsyncSession, query: str, skip_fast: bool = False) -> list[Product]:
    """쿼리에 해당하는 단일 Product에 모든 플랫폼 이벤트를 수집해 저장 (병렬)."""
    product = await _get_or_create_product(db, query, brand=None)
    # 신규 product commit → 독립 세션(_collect_platform)에서 조회 가능하도록
    await db.commit()
    await db.refresh(product)

    fresh = await _fresh_platforms(db, product)
    exclude = SKIP_SCRAPERS | (FAST_SCRAPERS if skip_fast else set())
    stale_platforms = [name for name in SCRAPERS if name not in fresh and name not in exclude]

    if not stale_platforms:
        return [product]

    await asyncio.gather(*[
        _collect_platform(product.id, name, query)
        for name in stale_platforms
    ])
    return [product]
