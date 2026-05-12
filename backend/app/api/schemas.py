from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ProductSummary(BaseModel):
    id: UUID
    name_kr: str | None
    name_en: str | None
    name_jp: str | None
    name_cn: str | None
    brand: str | None
    category: str | None


class SaleEventOut(BaseModel):
    id: UUID
    event_name: str | None
    event_type: str | None
    start_date: date | None
    end_date: date | None
    platform_name: str | None
    platform_country: str | None
    original_price: float | None
    sale_price: float | None
    discount_rate: float | None
    currency: str | None
    reason: str | None
    source_url: str | None
    confidence: float | None


class Recommendation(BaseModel):
    verdict: str  # "wait" | "buy_now" | "good_deal"
    reason: str
    next_event_name: str | None = None
    days_until_next: int | None = None
    expected_discount: float | None = None


class ProductEventsOut(BaseModel):
    product: ProductSummary
    events: list[SaleEventOut]
    recommendation: Recommendation
