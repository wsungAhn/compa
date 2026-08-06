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
    scraped_name: str | None = None
    is_bundle: bool = False


class Recommendation(BaseModel):
    verdict: str  # "wait" | "buy_now" | "good_deal"
    reason: str
    next_event_name: str | None = None
    days_until_next: int | None = None
    expected_discount: float | None = None
    # 가격 위치 — "지금 가격이 최대 할인에서 얼마나 떨어져 있나" (기존 필드는 그대로
    # 두어 프론트 계약을 깨지 않는다)
    current_price: float | None = None
    observed_min: float | None = None
    observed_max: float | None = None
    above_min_pct: float | None = None  # 관측 최저가 대비 몇 % 비싼가
    off_list_pct: float | None = None  # 정가 대비 할인율
    currency: str | None = None
    history_days: int | None = None  # 관측 기간 — 얕으면 얕다고 말한다
    sample_size: int | None = None


class SearchResponse(BaseModel):
    products: list[ProductSummary]
    job_id: str | None = None
    collecting: bool = False


# Backward compatibility alias
SearchOut = SearchResponse


class ProductEventsOut(BaseModel):
    product: ProductSummary
    events: list[SaleEventOut]
    recommendation: Recommendation
    premium: bool = False
