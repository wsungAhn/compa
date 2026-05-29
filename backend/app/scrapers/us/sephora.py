# Sephora(sephora.com) 할인 상품 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all cosmetics products that are on sale or have a discounted price. "
    "Include product name, brand, original price, sale price, discount percentage, currency (USD). "
    "Focus on items showing both a regular price and a reduced/sale price."
)


class SephoraScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Sephora"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 2.0
    EXTRACT_PROMPT = _PROMPT

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        url = f"https://www.sephora.com/search?keyword={query.replace(' ', '+')}"
        return await self.scrape_url(url, query)
