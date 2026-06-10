from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import SOCIAL_PLATFORM_NAME
from app.api.schemas import ProductEventsOut, ProductSummary, Recommendation, SaleEventOut, SearchOut
from app.core.affiliate import to_affiliate_url
from app.core.database import AsyncSessionLocal, get_db
from app.core.premium import premium_dep
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers.collector import collect_on_demand

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


@router.get("/search", response_model=SearchOut)
async def search_products(
    q: str = Query(..., min_length=1),
    lang: str = Query("ko", pattern="^(ko|en|ja|zh)$"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    col_map = {"ko": Product.name_kr, "en": Product.name_en, "ja": Product.name_jp, "zh": Product.name_cn}
    col = col_map[lang]

    # DB에서 먼저 조회
    result = await db.execute(
        select(Product)
        .where(col.ilike(f"%{q}%"), Product.deleted_at.is_(None))
        .limit(20)
    )
    products = list(result.scalars().all())

    if products:
        # Found in DB, return immediately with collecting=False
        return SearchOut(
            products=[ProductSummary.model_validate(p, from_attributes=True) for p in products],
            collecting=False,
        )

    # Not found in DB, schedule background collection if Korean and not already in-flight
    collecting = False
    if lang == "ko" and _should_schedule(q):
        background_tasks.add_task(_collect_in_background, q)
        collecting = True

    return SearchOut(products=[], collecting=collecting)


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
