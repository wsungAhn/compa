"""제품 할인 이벤트 수집기 — 다국가 스크래퍼 통합 실행."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import cast

from app.core.config import settings

from deep_translator import GoogleTranslator
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classifier import classify_rule_based
from app.ai.matcher import get_or_create_product, normalize_name
from app.core.database import AsyncSessionLocal
from app.core.url_safety import safe_url
from app.models.platform import Platform
from app.models.platform_product_id import PlatformProductId
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers.base import BaseScraper, ScrapedEvent
from app.scrapers.brands.shopify import BRAND_SCRAPERS
from app.scrapers.brands.amoremall import AmoremallScraper
from app.scrapers.brands.chantecaille_kr import ChantecailleKRScraper
from app.scrapers.brands.lamer_kr import LaMerKRScraper
from app.scrapers.cn.tmall import TmallScraper
from app.scrapers.cn.xiaohongshu import XiaohongshuScraper
from app.scrapers.jp.cosme import CosmeScraper
from app.scrapers.jp.rakuten import RakutenScraper
from app.scrapers.kr.coupang import CoupangScraper
from app.scrapers.kr.oliveyoung import OliveYoungScraper
from app.scrapers.us.amazon import AmazonScraper
from app.scrapers.us.sephora import SephoraScraper
from app.scrapers.us.shiseido import ShiseidoScraper
from app.scrapers.us.ulta import UltaScraper

# (ScraperClass, search_lang) — country-aware translation
SCRAPERS: dict[str, tuple[type[BaseScraper], str]] = {
    "올리브영":  (OliveYoungScraper, "ko"),
    "아모레몰":  (AmoremallScraper,  "ko"),
    "쿠팡":      (CoupangScraper,   "ko"),
    "Sephora":   (SephoraScraper,   "en"),
    "Ulta":      (UltaScraper,      "en"),
    "Amazon US": (AmazonScraper,    "en"),
    "Shiseido Official":       (ShiseidoScraper,       "en"),
    "La Mer Official KR":      (LaMerKRScraper,        "ko"),
    "Chantecaille Official KR":(ChantecailleKRScraper, "ko"),
    "Rakuten":   (RakutenScraper,   "ja"),
    "@cosme":    (CosmeScraper,     "ja"),
    "Tmall":     (TmallScraper,     "zh"),
    "小红书":    (XiaohongshuScraper,"zh"),
}

# 브랜드 공홈은 레지스트리에서 병합한다 — 브랜드를 늘릴 때 collector를 건드리지
# 않도록 (shopify.BRANDS 한 곳만 수정).
SCRAPERS.update({name: (cls, "en") for name, cls in BRAND_SCRAPERS.items()})

def get_enabled_scrapers() -> dict[str, tuple[type[BaseScraper], str]]:
    """settings.enabled_scrapers 기반 활성 스크래퍼 반환.

    "all" → SCRAPERS 전체, 아니면 이름 정확 일치 부분집합.
    미존재 이름은 무시 (예외 금지).
    """
    raw = settings.enabled_scrapers.strip()
    if raw.lower() == "all":
        return dict(SCRAPERS)
    names: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        # "brands" = 공홈 레지스트리 전체. 브랜드를 늘려도 설정을 안 고쳐도 된다.
        if token.lower() == "brands":
            names.extend(BRAND_SCRAPERS)
        else:
            names.append(token)
    return {name: SCRAPERS[name] for name in names if name in SCRAPERS}


CACHE_TTL_HOURS = 24
_BUNDLE_KEYWORDS = {"세트", "set", "kit", "duo", "bundle", "기획", "스페셜"}

# 403/503 차단으로 수집 불가한 플랫폼
SKIP_SCRAPERS: set[str] = set()

# 빠른 경로: REST API만 사용하는 플랫폼 (네이버쇼핑 종료 후 비어 있음)
FAST_SCRAPERS: set[str] = set()

# Browser 스크래퍼 목록 (semaphore 적용)
_BROWSER_SCRAPERS: set[str] = {
    "올리브영", "아모레몰", "Sephora", "Shiseido Official",
    "La Mer Official KR", "Chantecaille Official KR",
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


async def get_platform(db: AsyncSession, name: str) -> Platform | None:
    result = await db.execute(select(Platform).where(Platform.name == name))
    return result.scalar_one_or_none()


async def find_exact_for_sweep(
    db: AsyncSession,
    name: str,
    brand: str | None,
) -> Product | None:
    """스윕 전용 엄격 매처 — 브랜드 exact + name_en normalized exact만 허용."""
    if not brand or not name.strip():
        return None

    brand_lower = brand.strip().lower()
    normalized_name = normalize_name(name)

    result = await db.execute(
        select(Product).where(
            Product.deleted_at.is_(None),
            Product.brand.is_not(None),
            func.lower(Product.brand) == brand_lower,
        )
    )
    candidates = [
        candidate
        for candidate in result.scalars().all()
        if candidate.name_en and normalize_name(candidate.name_en) == normalized_name
    ]

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        _logger.warning(
            "sweep exact match ambiguous: brand=%s name=%s candidates=%d",
            brand,
            name,
            len(candidates),
        )
    return None


async def upsert_platform_product_id(
    db: AsyncSession,
    product_id: uuid.UUID,
    platform_id: uuid.UUID,
    external_id: str,
    id_type: str,
) -> uuid.UUID:
    """매핑을 upsert하고 최종적으로 authoritative한 product_id를 반환한다.

    - 기존 매핑이 없으면: 그대로 insert.
    - 기존 매핑이 있고 그 product가 살아있으면: product_id는 그대로 두고
      last_seen_at만 갱신 — 기존 product_id가 이긴다.
    - 기존 매핑이 있는데 그 product가 이미 소프트 삭제됐으면: 새
      product_id로 소유권을 재할당한다.

    호출자는 반환값을 실제 SaleEvent 저장에 쓸 product_id로 다시 사용해야 한다.
    """
    existing = (
        await db.execute(
            select(PlatformProductId.product_id, Product.deleted_at)
            .join(Product, Product.id == PlatformProductId.product_id)
            .where(
                PlatformProductId.platform_id == platform_id,
                PlatformProductId.external_id == external_id,
            )
        )
    ).first()

    if existing is not None:
        existing_product_id, deleted_at = existing
        if deleted_at is None:
            await db.execute(
                update(PlatformProductId)
                .where(
                    PlatformProductId.platform_id == platform_id,
                    PlatformProductId.external_id == external_id,
                )
                .values(last_seen_at=func.now())
            )
            return cast(uuid.UUID, existing_product_id)
        await db.execute(
            update(PlatformProductId)
            .where(
                PlatformProductId.platform_id == platform_id,
                PlatformProductId.external_id == external_id,
            )
            .values(product_id=product_id, last_seen_at=func.now())
        )
        return product_id

    stmt = pg_insert(PlatformProductId).values(
        product_id=product_id,
        platform_id=platform_id,
        external_id=external_id,
        id_type=id_type,
    ).on_conflict_do_nothing(index_elements=["platform_id", "external_id"])
    await db.execute(stmt)
    return product_id


async def find_by_external_id(
    db: AsyncSession,
    platform_id: uuid.UUID,
    external_id: str,
) -> Product | None:
    """external_id 하나로 활성 상품 조회. resolve_product_by_external_id가 호출한다."""
    result = await db.execute(
        select(Product)
        .join(PlatformProductId, PlatformProductId.product_id == Product.id)
        .where(
            PlatformProductId.platform_id == platform_id,
            PlatformProductId.external_id == external_id,
            Product.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def resolve_product_by_external_id(
    db: AsyncSession,
    platform_id: uuid.UUID,
    events: list[ScrapedEvent],
) -> Product | None:
    """이벤트 그룹의 신뢰 가능한 외부 식별자로 기존 활성 상품을 찾는다."""
    for s in events:
        if not s.external_id or s.id_type == "item_code":
            continue
        prod = await find_by_external_id(db, platform_id, s.external_id)
        if prod is not None:
            return prod
    return None


def group_events_by_product_name(events: list[ScrapedEvent]) -> dict[str, list[ScrapedEvent]]:
    """이름이 있는 이벤트만 상품명으로 묶는다."""
    grouped: dict[str, list[ScrapedEvent]] = {}
    for event in events:
        name = event.product_name.strip()
        if not name:
            continue
        grouped.setdefault(name, []).append(event)
    return grouped


async def persist_events_for_product(
    db: AsyncSession,
    product: Product,
    platform: Platform,
    scraped: list[ScrapedEvent],
) -> int:
    """한 상품의 이벤트를 저장하고 실제 insert된 행 수를 반환한다."""
    inserted = 0
    for s in scraped:
        if s.confidence == 0.0:
            continue

        authoritative_product_id = product.id
        if s.external_id:
            authoritative_product_id = await upsert_platform_product_id(
                db,
                product.id,
                platform.id,
                s.external_id,
                s.id_type or "unknown",
            )
            if authoritative_product_id != product.id:
                _logger.warning(
                    "external_id remapped sale event: platform=%s external_id=%s from_product=%s to_product=%s",
                    platform.name,
                    s.external_id,
                    product.id,
                    authoritative_product_id,
                )

        event_type = _classify_event_type(s)
        stmt = pg_insert(SaleEvent).values(
            id=uuid.uuid4(),
            product_id=authoritative_product_id,
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
            source_url=safe_url(s.source_url),
            confidence=s.confidence,
            needs_review=s.confidence < 0.7,
            scraped_name=s.product_name,
            size_ml=s.size_ml,
            is_bundle=_is_bundle(s.product_name),
            raw_text=s.raw_text,
        ).on_conflict_do_nothing().returning(SaleEvent.id)
        result = await db.execute(stmt)
        inserted += len(result.scalars().all())
    await db.commit()
    return inserted


def _get_platform_country(platform_name: str) -> str:
    """플랫폼 이름에서 country 코드 추정."""
    lang = SCRAPERS.get(platform_name, (None, "ko"))[1]
    return {"ko": "KR", "en": "US", "ja": "JP", "zh": "CN"}.get(lang, "KR")


async def _products_with_events(db: AsyncSession, product_ids: set[uuid.UUID]) -> list[Product]:
    """Return collected products that have at least one non-deleted event."""
    if not product_ids:
        return []

    result = await db.execute(
        select(Product)
        .join(SaleEvent, SaleEvent.product_id == Product.id)
        .where(
            Product.id.in_(product_ids),
            Product.deleted_at.is_(None),
            SaleEvent.deleted_at.is_(None),
        )
        .distinct()
    )
    return list(result.scalars().all())


async def _collect_platform(
    product_id: uuid.UUID,
    platform_name: str,
    query: str,
    platform_country: str,
    force: bool = False,
) -> set[uuid.UUID]:
    """단일 플랫폼 수집 (asyncio.gather 병렬 실행용)."""
    collected_product_ids: set[uuid.UUID] = set()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
        )
        product = result.scalar_one_or_none()
        if not product:
            return collected_product_ids

        platform = await get_platform(db, platform_name)
        if not platform:
            return collected_product_ids

        if not force:
            fresh = await _fresh_platforms(db, product)
            if platform_name in fresh:
                return collected_product_ids

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

            by_product = {
                product_name: events
                for product_name, events in group_events_by_product_name(scraped_events).items()
                if any(event.confidence > 0 for event in events)
            }

            for product_name, events in by_product.items():
                brand = events[0].brand if events else None
                prod = await resolve_product_by_external_id(db, platform.id, events)
                if prod is None:
                    prod = await get_or_create_product(db, product_name, brand, platform_country)
                await persist_events_for_product(db, prod, platform, events)
                collected_product_ids.add(prod.id)

        except Exception as exc:
            await db.rollback()
            _logger.warning("Platform %s scrape failed: %s", platform_name, exc)
    return collected_product_ids


async def collect_fast(db: AsyncSession, query: str) -> list[Product]:
    """빠른 경로: 활성 스크래퍼 중 FAST_SCRAPERS만 실행 (단일 REST 호출 플랫폼)."""
    enabled = get_enabled_scrapers()
    stale = [
        name for name in FAST_SCRAPERS
        if name not in SKIP_SCRAPERS and name in enabled
    ]
    # 수집할 게 없는데 product를 먼저 만들면 검색어마다 빈 placeholder가 쌓인다.
    if not stale:
        return []

    product = await get_or_create_product(db, query, None, "KR")
    await db.commit()
    await db.refresh(product)

    if stale:
        platform_country = _get_platform_country(stale[0])
        collected = await asyncio.gather(*[
            _collect_platform(product.id, name, query, platform_country)
            for name in stale
        ])
        product_ids = set().union(*collected)
        return await _products_with_events(db, product_ids)
    return []


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

    collected = await asyncio.gather(*[
        _collect_platform(product.id, name, query, _get_platform_country(name), force=force)
        for name in stale_platforms
    ])
    product_ids = set().union(*collected)
    collected_products = await _products_with_events(db, product_ids)

    if collected_products:
        return collected_products

    existing_ids = {p.id for p in existing}
    return await _products_with_events(db, existing_ids)
