import asyncio
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import SOCIAL_PLATFORM_NAME
from app.api.schemas import ProductEventsOut, ProductSummary, Recommendation, SaleEventOut, SearchResponse
from app.core.affiliate import to_affiliate_url
from app.core.database import AsyncSessionLocal, get_db
from app.core.limiter import limiter
from app.core.premium import premium_dep
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.models.search_log import SearchLog
from app.scrapers.collector import collect_fast, collect_on_demand

_MIN_COLLECT_LEN = 2
_TRGM_THRESHOLD = 0.25  # similarity() 임계값 (0~1, 낮을수록 느슨한 매칭)


async def _log_search(query: str, results_count: int, collecting: bool) -> None:
    """Background task: log search query. Swallows all errors. No PII stored."""
    try:
        async with AsyncSessionLocal() as db:
            log = SearchLog(
                query=query,
                lang="auto",
                results_count=results_count,
                collecting=collecting,
            )
            db.add(log)
            await db.commit()
    except Exception:
        pass


def _translate_query(q: str) -> str:
    """Sync translation function — call via asyncio.to_thread in async context."""
    try:
        from deep_translator import GoogleTranslator
        detected = GoogleTranslator(source="auto", target="en").translate(q)
        return str(detected) if detected and str(detected).lower() != q.lower() else q
    except Exception:
        return q


router = APIRouter(prefix="/api/products", tags=["products"])

# Track in-flight collection queries to avoid duplicate concurrent collections
_collecting_queries: set[str] = set()


def _should_schedule(query: str) -> bool:
    """Check if we should schedule a new collection for this query (not already in-flight)."""
    if query in _collecting_queries:
        return False
    _collecting_queries.add(query)
    return True


async def _collect_in_background(query: str) -> None:
    """Collect products in the background, with own DB session."""
    try:
        async with AsyncSessionLocal() as db:
            await collect_on_demand(db, query)
    except Exception:
        # Swallow exceptions
        pass
    finally:
        _collecting_queries.discard(query)


def _search_where(q: str) -> ColumnElement[bool]:
    """ILIKE + pg_trgm similarity + 단어AND 하이브리드 검색.

    검색 3계층:
    1. ILIKE "%q%" — 완전 부분 문자열 (가장 정확)
    2. trgm similarity > 0.25 — 오타·띄어쓰기 오류 보정
    3. 단어 AND — "설화수 쿠션" → name에 두 단어 모두 포함 (순서 무관)
    """
    ilike_clause = or_(
        Product.name_kr.ilike(f"%{q}%"),
        Product.name_en.ilike(f"%{q}%"),
        Product.name_jp.ilike(f"%{q}%"),
        Product.name_cn.ilike(f"%{q}%"),
    )
    # pg_trgm similarity: 오타·부분 일치 보정 (name_kr, name_en만 적용)
    trgm_clause = or_(
        func.similarity(Product.name_kr, q) > _TRGM_THRESHOLD,
        func.similarity(Product.name_en, q) > _TRGM_THRESHOLD,
    )
    # 단어 AND: 멀티 토큰 쿼리에서 각 단어가 모두 포함된 행 매칭
    tokens = [w for w in q.split() if len(w) >= 2]
    if len(tokens) > 1:
        word_and_kr = and_(*[Product.name_kr.ilike(f"%{t}%") for t in tokens])
        word_and_en = and_(*[Product.name_en.ilike(f"%{t}%") for t in tokens])
        return or_(ilike_clause, trgm_clause, word_and_kr, word_and_en)
    return or_(ilike_clause, trgm_clause)


def _search_order(q: str) -> list[Any]:
    """정렬 우선순위:
    1. 이벤트 보유 여부 (사용자가 수집한 제품 먼저)
    2. trgm similarity (검색어와 가까운 이름 먼저)
    """
    has_events = (
        select(func.count(SaleEvent.id))
        .where(SaleEvent.product_id == Product.id, SaleEvent.deleted_at.is_(None))
        .correlate(Product)
        .scalar_subquery()
    )
    trgm_score = func.greatest(
        func.coalesce(func.similarity(Product.name_kr, q), 0.0),
        func.coalesce(func.similarity(Product.name_en, q), 0.0),
    )
    return [has_events.desc(), trgm_score.desc()]


@router.get("/search", response_model=SearchResponse)
@limiter.limit("120/minute")
async def search_products(
    request: Request,
    q: str = Query(..., min_length=1),
    collect: bool = Query(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    # 1차: 원본 쿼리로 DB 탐색 (trgm fuzzy 포함)
    result = await db.execute(
        select(Product)
        .where(_search_where(q), Product.deleted_at.is_(None))
        .order_by(*_search_order(q))
        .limit(20)
    )
    products = list(result.scalars().all())

    # 2차: 결과 없으면 영어 번역 후 재탐색
    if not products:
        translated = await asyncio.to_thread(_translate_query, q)
        if translated != q:
            result2 = await db.execute(
                select(Product)
                .where(_search_where(translated), Product.deleted_at.is_(None))
                .order_by(*_search_order(translated))
                .limit(20)
            )
            products = list(result2.scalars().all())

    job_id: str | None = None
    collecting = False

    if collect and len(q.strip()) >= _MIN_COLLECT_LEN:
        # 빠른 경로: Naver만 동기 실행 (~1-2s) → 즉시 결과 반환
        fast_products = await collect_fast(db, q)

        # Celery: 나머지 플랫폼 (Playwright 기반) 비동기 디스패치
        try:
            from app.tasks.collect import run_collection_slow
            task = run_collection_slow.delay(q)  # type: ignore[attr-defined]
            job_id = task.id
            collecting = True
        except Exception:
            # Celery 미연결 환경 (테스트 등) — _should_schedule fallback
            if _should_schedule(q):
                background_tasks.add_task(_collect_in_background, q)
                collecting = True

        # fast_products로 업데이트 (Naver 결과 포함)
        if fast_products:
            products = fast_products

    result_products = [ProductSummary.model_validate(p, from_attributes=True) for p in products]
    background_tasks.add_task(_log_search, q, len(result_products), collecting)
    return SearchResponse(
        products=result_products,
        job_id=job_id,
        collecting=collecting,
    )


def _build_recommendation(events: list[SaleEvent]) -> Recommendation:
    today = date.today()

    # Check if current surprise event is active
    active_surprise = next(
        (e for e in events if e.event_type == "surprise" and e.start_date and e.end_date
         and e.start_date <= today <= e.end_date),
        None,
    )
    if active_surprise:
        return Recommendation(
            verdict="buy_now",
            reason="현재 돌발 할인 행사가 진행 중입니다.",
            expected_discount=float(active_surprise.discount_rate) if active_surprise.discount_rate else None,
        )

    # Check if current price is all-time low
    past_rates = [float(e.discount_rate) for e in events if e.discount_rate is not None]
    if past_rates:
        max_ever = max(past_rates)
        active_regular = next(
            (e for e in events if e.event_type == "regular" and e.start_date and e.end_date
             and e.start_date <= today <= e.end_date),
            None,
        )
        if active_regular and active_regular.discount_rate and float(active_regular.discount_rate) >= max_ever * 0.95:
            return Recommendation(
                verdict="buy_now",
                reason="현재 역대 최고 할인율 수준입니다.",
                expected_discount=float(active_regular.discount_rate),
            )

    # Find next upcoming regular event
    upcoming = [
        e for e in events
        if e.event_type == "regular" and e.start_date and e.start_date > today
    ]
    if upcoming:
        next_event = min(upcoming, key=lambda e: e.start_date or date.max)
        days_until = ((next_event.start_date or date.max) - today).days
        avg_discount = None
        rates = [
            float(e.discount_rate)
            for e in events
            if e.event_name == next_event.event_name and e.discount_rate is not None
        ]
        if rates:
            avg_discount = sum(rates) / len(rates)

        if days_until <= 60:
            return Recommendation(
                verdict="wait",
                reason=f"{next_event.event_name}까지 D-{days_until}. 기다리면 더 저렴하게 살 수 있습니다.",
                next_event_name=next_event.event_name,
                days_until_next=days_until,
                expected_discount=round(avg_discount, 1) if avg_discount else None,
            )

    # Default: good deal if any discount history exists
    if past_rates:
        avg = sum(past_rates) / len(past_rates)
        return Recommendation(
            verdict="good_deal",
            reason=f"과거 평균 할인율({avg:.0f}%)보다 나쁘지 않은 시점입니다.",
            expected_discount=round(avg, 1),
        )

    return Recommendation(verdict="good_deal", reason="할인 이력이 충분하지 않습니다. 현재 구매도 나쁘지 않습니다.")


@router.get("/{product_id}/events", response_model=ProductEventsOut)
async def get_product_events(
    product_id: UUID,
    years: int = Query(3, ge=1, le=5),
    country: str = Query("all"),
    db: AsyncSession = Depends(get_db),
    premium: bool = Depends(premium_dep),
) -> ProductEventsOut:
    product_result = await db.execute(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Force effective years to 1 for free tier
    effective_years = 1 if not premium else years

    since = date.today() - timedelta(days=365 * effective_years)
    stmt = (
        select(SaleEvent, Platform)
        .join(Platform, SaleEvent.platform_id == Platform.id)
        .where(
            SaleEvent.product_id == product_id,
            SaleEvent.deleted_at.is_(None),
            (SaleEvent.start_date >= since) | SaleEvent.start_date.is_(None),
        )
    )
    if country != "all":
        stmt = stmt.where(Platform.country == country.upper())

    # Exclude social platform events for free tier
    if not premium:
        social_platform_names = set(SOCIAL_PLATFORM_NAME.values())
        stmt = stmt.where(Platform.name.notin_(social_platform_names))

    result = await db.execute(stmt.order_by(SaleEvent.start_date.desc()))
    rows = result.all()

    events_out = [
        SaleEventOut(
            id=e.id,
            event_name=e.event_name,
            event_type=e.event_type,
            start_date=e.start_date,
            end_date=e.end_date,
            platform_name=p.name,
            platform_country=p.country,
            original_price=float(e.original_price) if e.original_price else None,
            sale_price=float(e.sale_price) if e.sale_price else None,
            discount_rate=float(e.discount_rate) if e.discount_rate else None,
            currency=e.currency,
            reason=e.reason,
            source_url=to_affiliate_url(e.source_url, p.name),
            confidence=e.confidence,
            scraped_name=e.scraped_name,
            is_bundle=bool(e.is_bundle),
        )
        for e, p in rows
    ]

    recommendation = _build_recommendation([e for e, _ in rows])

    return ProductEventsOut(
        product=ProductSummary.model_validate(product, from_attributes=True),
        events=events_out,
        recommendation=recommendation,
        premium=premium,
    )
