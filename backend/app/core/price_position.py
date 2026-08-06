"""가격 위치 — 지금 가격이 관측된 최저가에서 얼마나 떨어져 있는가.

판단 근거를 discount_rate·start_date(스크래핑으로 못 얻는 것)가 아니라
관측 가격 시계열(확실히 가진 것)에 둔다. 이력이 얕으면 얕다고 말한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Observation:
    """한 번의 가격 관측 (플랫폼별 수집 결과 1건)."""

    price: float
    observed_at: datetime
    list_price: float | None = None


@dataclass(frozen=True)
class PricePosition:
    current: float
    observed_min: float
    observed_max: float
    # 관측 최저가 대비 몇 % 비싼가. 0이면 역대 최저 수준.
    above_min_pct: float
    # 정가(list price) 대비 할인율. 정가 정보가 없으면 None.
    off_list_pct: float | None
    history_days: int
    sample_size: int

    @property
    def at_observed_low(self) -> bool:
        """관측 최저가에 사실상 붙어 있는가(2% 이내)."""
        return self.above_min_pct <= 2.0


def compute(observations: list[Observation]) -> PricePosition | None:
    """관측 시계열 → 가격 위치. 관측이 없으면 None."""
    usable = [o for o in observations if o.price and o.price > 0]
    if not usable:
        return None

    latest = max(usable, key=lambda o: o.observed_at)
    prices = [o.price for o in usable]
    low, high = min(prices), max(prices)

    above_min_pct = round((latest.price - low) / low * 100, 1) if low > 0 else 0.0

    off_list_pct: float | None = None
    if latest.list_price and latest.list_price > latest.price:
        off_list_pct = round((1 - latest.price / latest.list_price) * 100, 1)

    oldest = min(usable, key=lambda o: o.observed_at)
    span = latest.observed_at - oldest.observed_at
    # tz-naive/aware가 섞여 들어오면 비교에서 터진다 — 일수만 쓰므로 방어적으로 처리.
    history_days = max(span.days, 0)

    return PricePosition(
        current=round(latest.price, 2),
        observed_min=round(low, 2),
        observed_max=round(high, 2),
        above_min_pct=above_min_pct,
        off_list_pct=off_list_pct,
        history_days=history_days,
        sample_size=len(usable),
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
