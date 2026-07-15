"""Sephora 스크래퍼 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.scrapers.us.sephora import SephoraScraper, _parse_usd
from app.scrapers.us import sephora


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


@pytest.mark.asyncio
async def test_scrape_closes_browser_when_goto_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    browser = MagicMock()
    browser.close = AsyncMock()

    page = MagicMock()
    page.on = MagicMock()
    page.goto = AsyncMock(side_effect=RuntimeError("goto failed"))
    page.wait_for_timeout = AsyncMock()

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

    monkeypatch.setattr(sephora, "async_playwright", lambda: FakeAsyncPlaywright())

    scraper = SephoraScraper()
    events = await scraper.scrape("세럼")

    assert browser.close.await_count == 1
    assert len(events) == 1
    assert events[0].confidence == 0.0
