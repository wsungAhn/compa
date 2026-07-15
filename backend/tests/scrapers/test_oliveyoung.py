"""Olive Young 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.scrapers.kr.oliveyoung import OliveYoungScraper, _parse_date, _parse_price
from app.scrapers.kr import oliveyoung


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


@pytest.mark.asyncio
async def test_scrape_closes_browser_when_goto_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    browser = MagicMock()
    browser.close = AsyncMock()

    page = MagicMock()
    page.goto = AsyncMock(side_effect=RuntimeError("goto failed"))
    page.wait_for_timeout = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])

    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    browser.new_context = AsyncMock(return_value=context)

    class FakeAsyncPlaywright:
        def __init__(self) -> None:
            self.chromium = MagicMock()
            self.chromium.launch = AsyncMock(return_value=browser)

        async def __aenter__(self) -> "FakeAsyncPlaywright":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    monkeypatch.setattr(oliveyoung, "async_playwright", lambda: FakeAsyncPlaywright())

    scraper = OliveYoungScraper()
    events = await scraper.scrape("세럼")

    assert browser.close.await_count == 1
    assert len(events) == 1
    assert events[0].confidence == 0.0
