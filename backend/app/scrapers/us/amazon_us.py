# Amazon US(amazon.com) 뷰티 카테고리 할인 상품 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all cosmetics and beauty products with their prices. "
    "Include product name, brand, original price (list price), sale price (current price), "
    "discount rate if shown, currency (USD)."
)


class AmazonUSScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Amazon US"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 3.0
    EXTRACT_PROMPT = _PROMPT

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}&i=beauty"
        return await self.scrape_url(url, query)
