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


@dataclass(frozen=True)
class Prediction:
    """반복 관측에서 뽑은 다음 세일 주차."""

    recurrence_key: str
    iso_week: int
    years_observed: int
    week_spread: int  # 최대-최소(참고용). 이상치 하나에 무너지므로 판정엔 쓰지 않는다
    concentration: float  # 중앙값 ±1주 안에 들어온 연도 비율
    label: str | None

    @property
    def is_reliable(self) -> bool:
        """3년 이상 관측됐고 중앙값 ±1주에 70% 이상 몰릴 때만 D-day를 말한다.

        최대-최소 편차를 쓰면 이상치 하나가 판정을 뒤집는다 — 실측에서 블랙프라이데이
        11년치 중 10년이 W47~48인데 W28짜리 하울 하나 때문에 편차가 20으로 튀어
        "흔들림"으로 오판됐다. 집중도는 그 하나를 견딘다.
        """
        return self.years_observed >= 3 and self.concentration >= 0.7


def monday_of(iso_year: int, iso_week: int) -> date:
    return date.fromisocalendar(iso_year, min(max(iso_week, 1), 52), 1)


async def predict(db: AsyncSession, recurrence_key: str) -> Prediction | None:
    """연도 간 관측을 모아 이 행사가 몇 주차에 열리는지 추정한다.

    중앙값을 쓴다 — 한 해 이상치(코로나 해에 밀린 행사 등)가 평균을 끌고 가면
    사용자를 엉뚱한 주에 대기시킨다.
    """
    rows = (
        await db.execute(
            select(SaleWindow)
            .where(
                SaleWindow.recurrence_key == recurrence_key,
                SaleWindow.deleted_at.is_(None),
            )
            .order_by(SaleWindow.iso_year)
        )
    ).scalars().all()
    if not rows:
        return None

    by_year: dict[int, int] = {}
    for row in rows:
        by_year.setdefault(row.iso_year, row.iso_week)
    weeks = sorted(by_year.values())
    median = weeks[len(weeks) // 2]
    near = sum(1 for w in weeks if abs(w - median) <= 1)
    return Prediction(
        recurrence_key=recurrence_key,
        iso_week=median,
        years_observed=len(by_year),
        week_spread=weeks[-1] - weeks[0],
        concentration=round(near / len(weeks), 3),
        label=next((r.event_name for r in rows if r.event_name), None),
    )
