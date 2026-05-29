# 티몰(tmall.com) 할인 상품 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all cosmetics products with their prices. "
    "Include product name, brand, original price, sale price, discount rate, currency (CNY). "
    "Product names may be in Chinese."
)


class TmallScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Tmall"
    COUNTRY = "CN"
    RATE_LIMIT_SEC = 3.0
    EXTRACT_PROMPT = _PROMPT

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        url = f"https://list.tmall.com/search_product.htm?q={query.replace(' ', '+')}"
        return await self.scrape_url(url, query)
