"""가격 위치 + 세일 달력 기반 추천 판단 테스트."""
from datetime import date, datetime, timedelta, timezone

from app.api.products import _build_recommendation
from app.core import price_position, sale_calendar
from app.models.sale_event import SaleEvent


def _event(price: float, days_ago: int, list_price: float | None = None) -> SaleEvent:
    e = SaleEvent()
    e.sale_price = price
    e.original_price = list_price
    e.currency = "USD"
    e.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return e


# ── 세일 달력 ────────────────────────────────────────────────


def test_black_friday_is_the_friday_after_us_thanksgiving() -> None:
    # 2026-11-26이 넷째 목요일 → 블프는 11-27
    sales = sale_calendar.upcoming_sales(date(2026, 11, 1), country="US")
    bf = next(s for s in sales if s.name == "Black Friday")
    assert bf.when == date(2026, 11, 27)
    assert bf.days_until == 26


def test_cyber_monday_follows_black_friday() -> None:
    sales = sale_calendar.upcoming_sales(date(2026, 11, 1), country="US")
    bf = next(s for s in sales if s.name == "Black Friday")
    cm = next(s for s in sales if s.name == "Cyber Monday")
    assert (cm.when - bf.when).days == 3


def test_next_sale_rolls_into_the_following_year() -> None:
    """연말에는 다음 해 행사가 잡혀야 한다 — 없다고 답하면 안 된다."""
    nxt = sale_calendar.next_sale(date(2026, 12, 28), country="US")
    assert nxt is not None
    assert nxt.when.year == 2027


def test_country_filter_excludes_other_markets() -> None:
    names = {s.name for s in sale_calendar.upcoming_sales(date(2026, 1, 1), country="US")}
    assert "11.11 (光棍节)" not in names  # CN 전용
    assert "Black Friday" in names  # GLOBAL은 포함


# ── 가격 위치 ────────────────────────────────────────────────


def test_position_measures_distance_from_observed_low() -> None:
    now = price_position.now_utc()
    obs = [
        price_position.Observation(price=100.0, observed_at=now - timedelta(days=10)),
        price_position.Observation(price=80.0, observed_at=now - timedelta(days=5)),
        price_position.Observation(price=88.0, observed_at=now, list_price=110.0),
    ]
    pos = price_position.compute(obs)
    assert pos is not None
    assert pos.current == 88.0
    assert pos.observed_min == 80.0
    assert pos.observed_max == 100.0
    assert pos.above_min_pct == 10.0
    assert pos.off_list_pct == 20.0
    assert pos.history_days == 10
    assert not pos.at_observed_low


def test_position_without_observations_is_none() -> None:
    assert price_position.compute([]) is None


def test_list_price_below_current_is_not_a_discount() -> None:
    now = price_position.now_utc()
    pos = price_position.compute(
        [price_position.Observation(price=90.0, observed_at=now, list_price=50.0)]
    )
    assert pos is not None
    assert pos.off_list_pct is None


# ── 판단 ────────────────────────────────────────────────────


def test_no_price_observations_says_so() -> None:
    rec = _build_recommendation([])
    assert rec.verdict == "good_deal"
    assert "관측이 없습니다" in rec.reason


def test_at_observed_low_with_discount_is_buy_now() -> None:
    events = [_event(100.0, 10), _event(75.0, 0, list_price=103.0)]
    rec = _build_recommendation(events)
    assert rec.verdict == "buy_now"
    assert rec.off_list_pct == 27.2
    assert rec.observed_min == 75.0
    assert rec.currency == "USD"


def test_far_above_low_with_near_sale_is_wait() -> None:
    """관측 최저보다 비싸고 정기 세일이 가까우면 기다리라고 한다."""
    events = [_event(70.0, 30), _event(100.0, 0)]
    rec = _build_recommendation(events, country="US")
    assert rec.verdict == "wait"
    assert rec.days_until_next is not None and rec.days_until_next <= 60
    assert rec.above_min_pct is not None and rec.above_min_pct > 10


def test_shallow_history_is_reported_not_hidden() -> None:
    """하루치 관측으로 '역대 최저' 판정을 하지 않는다."""
    events = [_event(100.0, 0), _event(120.0, 0)]
    rec = _build_recommendation(events)
    assert rec.verdict == "good_deal"
    assert "이력이 0일" in rec.reason
    assert rec.history_days == 0


def test_position_fields_are_attached_to_every_verdict() -> None:
    events = [_event(100.0, 10), _event(75.0, 0, list_price=103.0)]
    rec = _build_recommendation(events)
    assert rec.current_price is not None
    assert rec.sample_size == 2


def test_country_drives_the_sale_calendar() -> None:
    """국가를 넘기면 그 시장의 달력을 쓴다 — 미국 상품에 11.11을 들이대지 않는다."""
    events = [_event(70.0, 30), _event(100.0, 0)]
    us = _build_recommendation(events, country="US")
    assert us.next_event_name is not None
    assert "11.11" not in us.next_event_name
