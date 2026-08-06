"""반복되는 정기 세일 달력.

스크래핑으로는 "다음 블랙프라이데이가 언제인지"가 오지 않는다. 오는 것은 오늘
시점의 가격뿐이다. 반복 세일은 규칙으로 열거 가능하므로 달력에 박아두고 계산한다
(Deterministic First — LLM도 스크래핑도 개입하지 않는다).
"""
from __future__ import annotations

import calendar
import json
import pathlib
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


# 날짜가 규칙으로 확정되는 행사만 여기 남긴다. 해마다 움직이는 행사(Sephora 세일,
# 프라임데이)를 고정일로 근사하면 "세일 없음"이 아니라 **틀린 D-day를 자신 있게**
# 말하게 된다(적대감사 R1). 그런 행사는 아래 MEASURED 쪽에서 월 단위로만 다룬다.
RULES: list[tuple[str, object, str]] = [
    ("Black Friday", _black_friday, GLOBAL),
    ("Cyber Monday", _cyber_monday, GLOBAL),
    ("Memorial Day Sale", lambda y: _nth_weekday(y, 5, 0, 4), "US"),
    ("Labor Day Sale", lambda y: _nth_weekday(y, 9, 0, 1), "US"),
    ("11.11 (光棍节)", _fixed(11, 11), "CN"),
    ("6.18", _fixed(6, 18), "CN"),
    ("楽天スーパーSALE", _fixed(3, 4), "JP"),
    ("Boxing Day", _fixed(12, 26), GLOBAL),
]


_MEASURED_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "sale_timing.json"
# 관측이 이 월에 몰려야 캘린더에 쓴다. 아래는 sale_timing.TimingEstimate.is_confident와
# 같은 기준이며, 신뢰 못 할 항목은 아예 말하지 않는 쪽을 택한다.
_MEASURED_COUNTRY = "US"


@dataclass(frozen=True)
class ApproximateSale:
    """월 단위로만 아는 행사. 정확한 날짜를 지어내지 않는다."""

    name: str
    month: int
    share: float
    sample_size: int
    corroborations: int = 1  # 이 달을 가리킨 독립 쿼리 수


def measured_sales() -> list[ApproximateSale]:
    """하울 영상 업로드 분포에서 관측된 세일 시기(scripts/refresh_sale_timing.py).

    서로 다른 쿼리가 같은 달을 가리키면 **버리지 않고 합친다**. 라벨이 틀렸다고
    관측까지 틀린 게 아니다 — 실측에서 "sephora fall sale haul"이 봄 하울까지
    긁어와 4월로 나왔는데, 그건 가을 행사가 4월이라는 뜻이 아니라 **4월에 대한
    독립적인 두 번째 증거**다. 표본을 합산하고 몇 개 쿼리가 지지했는지 남긴다.
    """
    if not _MEASURED_PATH.is_file():
        return []
    try:
        records = json.loads(_MEASURED_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    merged: dict[int, ApproximateSale] = {}
    for rec in records:
        if not rec.get("confident"):
            continue
        name, month = str(rec.get("event", "")), int(rec.get("peak_month", 0))
        if not name or not 1 <= month <= 12:
            continue
        share = float(rec.get("share", 0.0))
        size = int(rec.get("sample_size", 0))
        prior = merged.get(month)
        if prior is None:
            merged[month] = ApproximateSale(name=name, month=month, share=share, sample_size=size)
            continue
        total = prior.sample_size + size
        merged[month] = ApproximateSale(
            # 라벨은 더 많은 표본이 지지하는 쪽을 쓴다. 둘 다 같은 달을 봤으므로
            # 어느 라벨이 정확한지는 관측이 답해주지 않는다.
            name=prior.name if prior.sample_size >= size else name,
            month=month,
            share=round((prior.share * prior.sample_size + share * size) / total, 3) if total else 0.0,
            sample_size=total,
            corroborations=prior.corroborations + 1,
        )
    return sorted(merged.values(), key=lambda s: s.month)


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
