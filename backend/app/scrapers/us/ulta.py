# Ulta(ulta.com) 할인 상품 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all cosmetics and beauty products that are on sale or discounted. "
    "Include product name, brand, original price, sale price, discount rate, currency (USD)."
)


class UltaScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Ulta"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 2.0
    EXTRACT_PROMPT = _PROMPT

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        url = f"https://www.ulta.com/search?search={query.replace(' ', '+')}"
        return await self.scrape_url(url, query)
