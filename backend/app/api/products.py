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
from app.core.url_safety import safe_url
from app.core.price_position import Observation, compute as compute_position
from app.core.sale_calendar import next_sale
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


def _build_recommendation(events: list[SaleEvent], country: str | None = None) -> Recommendation:
    """가격 위치 + 정기 세일 달력으로 판단.

    이전 구현은 event_type/start_date/end_date에 의존했는데, 스크래핑으로는 미래
    세일 일정도 행사 종료일도 오지 않는다(실측: end_date 0건, start_date는 전부
    수집일). 그래서 세 분기가 모두 죽고 폴백 문구만 나갔다. 판단 근거를 관측
    가격 시계열과 규칙으로 열거되는 세일 달력으로 옮긴다.
    """
    today = date.today()
    observations = [
        Observation(
            price=float(e.sale_price),
            observed_at=e.created_at,
            list_price=float(e.original_price) if e.original_price else None,
        )
        for e in events
        if e.sale_price
    ]
    position = compute_position(observations)
    upcoming = next_sale(today, country)
    currency = next((e.currency for e in events if e.currency), None)

    def _with_position(rec: Recommendation) -> Recommendation:
        if not position:
            return rec
        return rec.model_copy(update={
            "current_price": position.current,
            "observed_min": position.observed_min,
            "observed_max": position.observed_max,
            "above_min_pct": position.above_min_pct,
            "off_list_pct": position.off_list_pct,
            "currency": currency,
            "history_days": position.history_days,
            "sample_size": position.sample_size,
        })

    if not position:
        return Recommendation(
            verdict="good_deal",
            reason="아직 가격 관측이 없습니다. 수집이 끝나면 다시 확인해 보세요.",
        )

    shallow = position.history_days < 3

    # 정가(compare_at_price)는 판매자가 넣는 값이라 그대로 믿을 수 없다. 세트 상품은
    # "정가"가 구성품 합계라 상시 할인처럼 보인다(실측 2026-08-05: MERIT는 카탈로그의
    # 81.9%가 '할인 중', 예: 세트 $90 vs "정가" $100). 번들이면 정가를 신뢰하지 않는다.
    trustworthy_list_price = position.off_list_pct and not any(e.is_bundle for e in events)

    if trustworthy_list_price and (shallow or position.at_observed_low):
        reason = f"정가 대비 {position.off_list_pct:.0f}% 할인 중입니다."
        if not shallow:
            reason += f" 관측된 최저가({position.observed_min:,.0f}) 수준입니다."
        return _with_position(Recommendation(
            verdict="buy_now",
            reason=reason,
            expected_discount=position.off_list_pct,
        ))

    # 이력이 얕으면 "최저가보다 비싸다/싸다"를 주장하지 않는다. 하루치 변동은
    # 노이즈이고, 그걸로 기다리라고 하면 사용자를 잘못 붙잡아 둔다.
    if shallow:
        return _with_position(Recommendation(
            verdict="good_deal",
            reason=(
                f"관측 이력이 {position.history_days}일({position.sample_size}건)로 짧아 "
                "최저가 판단이 이릅니다. 며칠 뒤 다시 확인해 보세요."
            ),
            next_event_name=upcoming.name if upcoming else None,
            days_until_next=upcoming.days_until if upcoming else None,
        ))

    # 최저가보다 눈에 띄게 비싼데 정기 세일이 가까우면 기다릴 값어치가 있다.
    if position.above_min_pct >= 10 and upcoming and upcoming.days_until <= 60:
        return _with_position(Recommendation(
            verdict="wait",
            reason=(
                f"지금은 관측 최저가보다 {position.above_min_pct:.0f}% 비쌉니다. "
                f"{upcoming.name}까지 D-{upcoming.days_until}."
            ),
            next_event_name=upcoming.name,
            days_until_next=upcoming.days_until,
        ))

    if position.at_observed_low:
        return _with_position(Recommendation(
            verdict="buy_now",
            reason=f"관측된 최저가({position.observed_min:,.0f}) 수준입니다.",
            # 신뢰할 수 없는 정가를 할인율로 되돌려 내보내지 않는다.
            expected_discount=position.off_list_pct if trustworthy_list_price else None,
        ))

    return _with_position(Recommendation(
        verdict="good_deal",
        reason=(
            f"관측 최저가보다 {position.above_min_pct:.0f}% 높지만 "
            f"최고가({position.observed_max:,.0f}) 대비로는 낮은 편입니다."
        ),
        next_event_name=upcoming.name if upcoming else None,
        days_until_next=upcoming.days_until if upcoming else None,
    ))


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
            source_url=to_affiliate_url(safe_url(e.source_url), p.name),
            confidence=e.confidence,
            scraped_name=e.scraped_name,
            is_bundle=bool(e.is_bundle),
        )
        for e, p in rows
    ]

    # 세일 달력은 국가별로 다르다 — 이 상품이 실제로 관측된 플랫폼의 국가를 쓴다.
    countries: list[str] = [p.country for _e, p in rows if p.country]
    event_country = max(set(countries), key=countries.count) if countries else None
    recommendation = _build_recommendation([e for e, _ in rows], country=event_country)

    return ProductEventsOut(
        product=ProductSummary.model_validate(product, from_attributes=True),
        events=events_out,
        recommendation=recommendation,
        premium=premium,
    )
