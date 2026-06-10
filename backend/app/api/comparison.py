from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.fx import convert
from app.models.platform import Platform
from app.models.product import Product
from app.models.sale_event import SaleEvent

router = APIRouter(prefix="/api/products", tags=["comparison"])


class PlatformPrice(BaseModel):
    platform_name: str
    platform_country: str
    sale_price: float | None
    original_price: float | None
    discount_rate: float | None
    currency: str | None
    event_name: str | None
    source_url: str | None
    converted_price: float | None  # sale_price converted to preferred platform's currency
    saving_vs_preferred: float | None  # 양수 = preferred가 더 비쌈 (이쪽이 저렴)


class ComparisonOut(BaseModel):
    product_name: str
    preferred: PlatformPrice | None
    alternatives: list[PlatformPrice]
    cheapest_platform: str | None
    cheapest_saving_pct: float | None  # preferred 대비 절감율


async def _latest_price(
    db: AsyncSession, product_id: UUID, platform_id: UUID
) -> SaleEvent | None:
    result = await db.execute(
        select(SaleEvent)
        .where(
            SaleEvent.product_id == product_id,
            SaleEvent.platform_id == platform_id,
            SaleEvent.deleted_at.is_(None),
            SaleEvent.sale_price.is_not(None),
        )
        .order_by(SaleEvent.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/{product_id}/comparison", response_model=ComparisonOut)
async def get_price_comparison(
    product_id: UUID,
    preferred: str = Query(..., description="선호 플랫폼명 (예: 네이버쇼핑)"),
    platforms: str = Query("all", description="비교할 플랫폼 목록 (쉼표 구분, 기본 all)"),
    db: AsyncSession = Depends(get_db),
) -> ComparisonOut:
    product_result = await db.execute(
        select(Product).where(Product.id == product_id, Product.deleted_at.is_(None))
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 플랫폼 목록 조회
    if platforms == "all":
        platform_result = await db.execute(select(Platform))
        all_platforms = list(platform_result.scalars().all())
    else:
        names = [p.strip() for p in platforms.split(",")]
        platform_result = await db.execute(
            select(Platform).where(Platform.name.in_(names))
        )
        all_platforms = list(platform_result.scalars().all())

    # 각 플랫폼 최신 가격 수집
    platform_prices: list[tuple[Platform, SaleEvent]] = []
    for p in all_platforms:
        event = await _latest_price(db, product_id, p.id)
        if event:
            platform_prices.append((p, event))

    def to_platform_price(
        p: Platform,
        e: SaleEvent,
        preferred_currency: str | None,
        preferred_converted_price: float | None,
    ) -> PlatformPrice:
        # Convert sale_price to preferred currency if applicable
        converted_price: float | None = None
        if e.sale_price and e.currency and preferred_currency:
            if e.currency == preferred_currency:
                converted_price = float(e.sale_price)
            else:
                converted_price = convert(float(e.sale_price), e.currency, preferred_currency)

        # Calculate saving using converted prices
        saving: float | None = None
        if preferred_converted_price and converted_price:
            saving = round(preferred_converted_price - converted_price, 2)

        return PlatformPrice(
            platform_name=p.name,
            platform_country=p.country,
            sale_price=float(e.sale_price) if e.sale_price else None,
            original_price=float(e.original_price) if e.original_price else None,
            discount_rate=float(e.discount_rate) if e.discount_rate else None,
            currency=e.currency,
            event_name=e.event_name,
            source_url=e.source_url,
            converted_price=converted_price,
            saving_vs_preferred=saving,
        )

    # 선호 플랫폼 분리 및 preferred_currency 결정
    preferred_pp: PlatformPrice | None = None
    preferred_currency: str | None = None
    preferred_converted_price: float | None = None
    alternatives: list[PlatformPrice] = []

    for p, e in platform_prices:
        if p.name == preferred:
            preferred_currency = e.currency
            preferred_converted_price = float(e.sale_price) if e.sale_price else None
            preferred_pp = to_platform_price(p, e, preferred_currency, None)

    # saving 계산 포함 alternatives 생성 (선호 제외, 모든 통화 포함)
    for p, e in platform_prices:
        if p.name != preferred:
            alternatives.append(
                to_platform_price(p, e, preferred_currency, preferred_converted_price)
            )

    # 전체 대안을 converted_price 기준으로 정렬 (저렴한 순), None 값은 마지막
    alternatives.sort(
        key=lambda x: (x.converted_price is None, x.converted_price or float("inf"))
    )

    # 최저가 플랫폼 — converted_price 기반
    cheapest: PlatformPrice | None = None
    cheapest_saving_pct: float | None = None
    if alternatives:
        cheapest = alternatives[0]

    if (
        cheapest
        and preferred_converted_price
        and cheapest.converted_price
        and preferred_converted_price > 0
    ):
        cheapest_saving_pct = round(
            (preferred_converted_price - cheapest.converted_price)
            / preferred_converted_price
            * 100,
            1,
        )

    return ComparisonOut(
        product_name=product.name_kr or product.name_en or "",
        preferred=preferred_pp,
        alternatives=alternatives,
        cheapest_platform=cheapest.platform_name if cheapest and (cheapest.saving_vs_preferred or 0) > 0 else None,
        cheapest_saving_pct=cheapest_saving_pct if cheapest_saving_pct and cheapest_saving_pct > 0 else None,
    )
