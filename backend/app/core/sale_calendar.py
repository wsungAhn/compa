"""반복되는 정기 세일 달력.

스크래핑으로는 "다음 블랙프라이데이가 언제인지"가 오지 않는다. 오는 것은 오늘
시점의 가격뿐이다. 반복 세일은 규칙으로 열거 가능하므로 달력에 박아두고 계산한다
(Deterministic First — LLM도 스크래핑도 개입하지 않는다).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

GLOBAL = "GLOBAL"


@dataclass(frozen=True)
class SaleEvent:
    name: str
    when: date
    country: str
    days_until: int


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """그 달의 n번째 특정 요일. weekday는 월=0 … 일=6."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + (n - 1) * 7)


def _thanksgiving(year: int) -> date:
    """미국 추수감사절 = 11월 넷째 목요일."""
    return _nth_weekday(year, 11, 3, 4)


def _black_friday(year: int) -> date:
    return date.fromordinal(_thanksgiving(year).toordinal() + 1)


def _cyber_monday(year: int) -> date:
    return date.fromordinal(_black_friday(year).toordinal() + 3)


def _fixed(month: int, day: int):  # type: ignore[no-untyped-def]
    def rule(year: int) -> date:
        # 2월 29일 등 없는 날짜는 그 달 말일로 내린다.
        last = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last))

    return rule


# (이름, 연도→날짜 규칙, 대상 국가)
# 날짜가 해마다 바뀌는 행사(프라임데이 등)는 통상 시기로 근사한다 — D-day의 목적은
# "기다릴 만한가"이지 예약이 아니다.
RULES: list[tuple[str, object, str]] = [
    ("Black Friday", _black_friday, GLOBAL),
    ("Cyber Monday", _cyber_monday, GLOBAL),
    ("Amazon Prime Day", _fixed(7, 16), "US"),
    ("Sephora Savings Event (봄)", _fixed(4, 5), "US"),
    ("Sephora Savings Event (가을)", _fixed(10, 25), "US"),
    ("Memorial Day Sale", lambda y: _nth_weekday(y, 5, 0, 4), "US"),
    ("Labor Day Sale", lambda y: _nth_weekday(y, 9, 0, 1), "US"),
    ("11.11 (光棍节)", _fixed(11, 11), "CN"),
    ("6.18", _fixed(6, 18), "CN"),
    ("楽天スーパーSALE", _fixed(3, 4), "JP"),
    ("Boxing Day", _fixed(12, 26), GLOBAL),
]


def upcoming_sales(today: date, country: str | None = None, horizon_days: int = 365) -> list[SaleEvent]:
    """오늘 이후 horizon_days 이내의 세일을 가까운 순으로 반환."""
    found: list[SaleEvent] = []
    for name, rule, target in RULES:
        if country and target not in (country, GLOBAL):
            continue
        for year in (today.year, today.year + 1):
            when = rule(year)  # type: ignore[operator]
            delta = (when - today).days
            if 0 <= delta <= horizon_days:
                found.append(SaleEvent(name=name, when=when, country=target, days_until=delta))
                break
    return sorted(found, key=lambda s: s.days_until)


def next_sale(today: date, country: str | None = None) -> SaleEvent | None:
    """가장 가까운 다음 정기 세일."""
    sales = upcoming_sales(today, country)
    return sales[0] if sales else None
