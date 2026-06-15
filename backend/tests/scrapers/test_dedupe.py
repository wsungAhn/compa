"""Deduplication logic unit tests."""
from datetime import date

from app.scrapers.base import ScrapedEvent
from app.scrapers.collector import _event_signature


def test_event_signature_equal_events() -> None:
    """Same event parameters produce same signature."""
    s1 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    s2 = ScrapedEvent(
        product_name="크림",  # Different product name doesn't affect signature
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    assert _event_signature(s1) == _event_signature(s2)


def test_event_signature_different_event_name() -> None:
    """Different event name produces different signature."""
    s1 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    s2 = ScrapedEvent(
        product_name="에센스",
        event_name="특가",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    assert _event_signature(s1) != _event_signature(s2)


def test_event_signature_different_sale_price() -> None:
    """Different sale price produces different signature."""
    s1 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    s2 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=35000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    assert _event_signature(s1) != _event_signature(s2)


def test_event_signature_different_original_price() -> None:
    """Different original price produces different signature."""
    s1 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    s2 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=55000.0,
        start_date=date(2024, 1, 1),
    )
    assert _event_signature(s1) != _event_signature(s2)


def test_event_signature_different_start_date() -> None:
    """Different start date produces different signature."""
    s1 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    s2 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 2),
    )
    assert _event_signature(s1) != _event_signature(s2)


def test_event_signature_with_none_prices() -> None:
    """Handles None prices correctly in signature."""
    s1 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=None,
        original_price=None,
        start_date=date(2024, 1, 1),
    )
    s2 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=None,
        original_price=None,
        start_date=date(2024, 1, 1),
    )
    assert _event_signature(s1) == _event_signature(s2)


def test_event_signature_one_price_none() -> None:
    """Different when one price is None and other isn't."""
    s1 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=None,
        start_date=date(2024, 1, 1),
    )
    s2 = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=None,
        original_price=None,
        start_date=date(2024, 1, 1),
    )
    assert _event_signature(s1) != _event_signature(s2)


def test_event_signature_tuple_format() -> None:
    """Signature returns correct tuple format (event_name, sale_price, original_price, start_date)."""
    s = ScrapedEvent(
        product_name="에센스",
        event_name="올영세일",
        sale_price=29000.0,
        original_price=50000.0,
        start_date=date(2024, 1, 1),
    )
    sig = _event_signature(s)
    assert len(sig) == 4
    assert sig[0] == "올영세일"
    assert sig[1] == 29000.0
    assert sig[2] == 50000.0
    assert sig[3] == date(2024, 1, 1)
