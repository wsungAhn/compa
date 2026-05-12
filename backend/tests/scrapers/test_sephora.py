"""Sephora 스크래퍼 단위 테스트."""
from app.scrapers.us.sephora import SephoraScraper, _parse_usd


def test_parse_usd_standard() -> None:
    assert _parse_usd("$45.00") == 45.0


def test_parse_usd_no_cents() -> None:
    assert _parse_usd("$120") == 120.0


def test_parse_usd_none() -> None:
    assert _parse_usd("Price unavailable") is None


def test_scraper_attrs() -> None:
    s = SephoraScraper()
    assert s.PLATFORM_NAME == "Sephora"
    assert s.COUNTRY == "US"
    assert s.RATE_LIMIT_SEC == 1.5
