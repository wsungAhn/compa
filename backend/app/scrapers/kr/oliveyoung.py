# 올리브영(oliveyoung.co.kr) 할인 상품 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all cosmetics products with their prices. "
    "Include product name, brand, original price, sale price, discount rate, currency (KRW). "
    "Product names may be in Korean."
)


class OliveYoungScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Olive Young"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 2.0
    EXTRACT_PROMPT = _PROMPT

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        url = f"https://www.oliveyoung.co.kr/store/search/getSearchMain.do?query={query.replace(' ', '+')}"
        return await self.scrape_url(url, query)
