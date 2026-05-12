"""네이버쇼핑 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.kr.naver_shop import NaverShopItem, NaverShopScraper


def test_scraper_platform_attrs() -> None:
    scraper = NaverShopScraper()
    assert scraper.PLATFORM_NAME == "네이버쇼핑"
    assert scraper.COUNTRY == "KR"


def test_naver_shop_item_fields() -> None:
    item = NaverShopItem(
        title="설화수 <b>퍼펙팅</b> 쿠션",
        brand="설화수",
        lprice=45000,
        hprice=60000,
        mall_name="올리브영",
        product_id="12345",
        product_url="https://example.com",
        category="스킨케어",
    )
    assert item.lprice == 45000
    assert item.brand == "설화수"


@pytest.mark.asyncio
async def test_scrape_cleans_html_tags() -> None:
    scraper = NaverShopScraper()
    mock_items = [
        NaverShopItem(
            title="설화수 <b>퍼펙팅</b> 쿠션",
            brand="설화수",
            lprice=45000,
            hprice=60000,
            mall_name="올리브영",
            product_id="1",
            product_url="https://example.com",
            category="스킨케어",
        )
    ]
    with patch.object(scraper, "_search_products", new=AsyncMock(return_value=mock_items)):
        events = await scraper.scrape("설화수")

    assert len(events) == 1
    assert "<b>" not in events[0].product_name
    assert events[0].sale_price == 45000.0
