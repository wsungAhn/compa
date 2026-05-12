"""Olive Young 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
import pytest

from app.scrapers.kr.oliveyoung import OliveYoungScraper, _parse_date, _parse_price


def test_parse_price_with_comma() -> None:
    assert _parse_price("12,000원") == 12000.0


def test_parse_price_plain() -> None:
    assert _parse_price("9900") == 9900.0


def test_parse_price_none() -> None:
    assert _parse_price("가격 미정") is None


def test_parse_date_dot_format() -> None:
    from datetime import date
    assert _parse_date("2024.11.22") == date(2024, 11, 22)


def test_parse_date_dash_format() -> None:
    from datetime import date
    assert _parse_date("2024-06-18") == date(2024, 6, 18)


def test_parse_date_none() -> None:
    assert _parse_date("날짜 없음") is None


def test_scraper_platform_attrs() -> None:
    scraper = OliveYoungScraper()
    assert scraper.PLATFORM_NAME == "Olive Young"
    assert scraper.COUNTRY == "KR"
    assert scraper.RATE_LIMIT_SEC == 1.0
