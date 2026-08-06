"""세일 창 기록 — 모든 소스가 같은 슬롯에 쌓이게 하는 단일 입구.

각 소스가 제 방식대로 테이블에 쓰기 시작하면 스코프·출처 표기가 곧 갈라진다.
기록은 여기로만 들어온다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sale_window import SaleWindow

# 사이트와이드 여부는 사용자 행동을 바꾼다 — 같은 25%라도 값어치가 다르다.
_SITEWIDE_RE = re.compile(r"\bsite\s?wide\b|\bstorewide\b|\bentire (?:site|store|order)\b", re.I)
_CATEGORY_RE = re.compile(r"\ball\b .{0,20}\b(?:skincare|makeup|fragrance|haircare)\b", re.I)
_DISCOUNT_RE = re.compile(r"(\d{1,2})\s?%\s?off|\bextra\s+(\d{1,2})\s?%", re.I)


@dataclass(frozen=True)
class Observation:
    brand: str
    source: str
    on: date
    event_name: str | None = None
    discount_pct: float | None = None
    price: float | None = None
    currency: str | None = None
    retailer: str | None = None
    country: str | None = None
    source_url: str | None = None
    is_estimate: bool = False
    sample_size: int | None = None
    corroborations: int = 1
    confidence: float | None = None
    recurrence_key: str | None = None
    scope: str | None = None


def classify_scope(title: str) -> str:
    """제목에서 세일 범위를 읽는다. 모르면 'unknown' — 지어내지 않는다."""
    if _SITEWIDE_RE.search(title):
        return "sitewide"
    if _CATEGORY_RE.search(title):
        return "category"
    return "item" if title.strip() else "unknown"


def parse_discount_pct(title: str) -> float | None:
    match = _DISCOUNT_RE.search(title)
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if 0 < value < 100 else None


def week_of(day: date) -> tuple[int, int]:
    """ISO 연도·주차. 연말연시 경계를 달력 연도로 세면 어긋난다."""
    iso = day.isocalendar()
    return iso[0], iso[1]


async def record(db: AsyncSession, obs: Observation) -> SaleWindow | None:
    """관측 1건을 슬롯에 기록. 같은 출처·URL이 이미 있으면 건너뛴다."""
    if obs.source_url:
        existing = await db.execute(
            select(SaleWindow).where(
                SaleWindow.source == obs.source,
                SaleWindow.source_url == obs.source_url,
            )
        )
        if existing.scalar_one_or_none():
            return None

    iso_year, iso_week = week_of(obs.on)
    window = SaleWindow(
        iso_year=iso_year,
        iso_week=iso_week,
        # 추정이면 날짜를 아는 척하지 않는다.
        observed_on=None if obs.is_estimate else obs.on,
        brand=obs.brand,
        event_name=obs.event_name,
        discount_pct=obs.discount_pct,
        price=obs.price,
        currency=obs.currency,
        scope=obs.scope or "unknown",
        retailer=obs.retailer,
        country=obs.country,
        source=obs.source,
        source_url=obs.source_url,
        is_estimate=obs.is_estimate,
        sample_size=obs.sample_size,
        corroborations=obs.corroborations,
        confidence=obs.confidence,
        recurrence_key=obs.recurrence_key,
    )
    db.add(window)
    return window
