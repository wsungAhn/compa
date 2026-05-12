from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ProductEventsOut, ProductSummary, Recommendation, SaleEventOut
from app.core.database import get_db
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers.collector import collect_on_demand

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/search", response_model=list[ProductSummary])
async def search_products(
    q: str = Query(..., min_length=1),
    lang: str = Query("ko", pattern="^(ko|en|ja|zh)$"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
) -> list[ProductSummary]:
    col_map = {"ko": Product.name_kr, "en": Product.name_en, "ja": Product.name_jp, "zh": Product.name_cn}
    col = col_map[lang]

    # DB에서 먼저 조회
    result = await db.execute(
        select(Product)
        .where(col.ilike(f"%{q}%"), Product.deleted_at.is_(None))
        .limit(20)
    )
    products = list(result.scalars().all())

    if not products:
        # DB에 없으면 온디맨드 수집 (한국어 검색만)
        if lang == "ko":
            products = await collect_on_demand(db, q)

    return [ProductSummary.model_validate(p, from_attributes=True) for p in products]


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
        next_event = min(upcoming, key=lambda e: e.start_date)  # type: ignore[arg-type]
        days_until = (next_event.start_date - today).days  # type: ignore[operator]
        avg_discount = None
        same_name = [e for e in events if e.event_name == next_event.event_name and e.discount_rate]
        if same_name:
            avg_discount = sum(float(e.discount_rate) for e in same_name) / len(same_name)  # type: ignore[arg-type]

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
) -> ProductEventsOut:
    product_result = await db.execute(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    since = date.today() - timedelta(days=365 * years)
    stmt = (
        select(SaleEvent, Platform)
        .join(Platform, SaleEvent.platform_id == Platform.id)
        .where(
            SaleEvent.product_id == product_id,
            SaleEvent.deleted_at.is_(None),
            SaleEvent.start_date >= since,
        )
    )
    if country != "all":
        stmt = stmt.where(Platform.country == country.upper())

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
            source_url=e.source_url,
            confidence=e.confidence,
        )
        for e, p in rows
    ]

    recommendation = _build_recommendation([e for e, _ in rows])

    return ProductEventsOut(
        product=ProductSummary.model_validate(product, from_attributes=True),
        events=events_out,
        recommendation=recommendation,
    )
