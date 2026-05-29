# 소홍서(xiaohongshu.com) 할인 정보 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all cosmetics discount or sale information from social posts. "
    "Include product name, brand, sale price, discount rate, currency (CNY). "
    "Content may be in Chinese."
)


class XiaohongshuScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "小红书"
    COUNTRY = "CN"
    RATE_LIMIT_SEC = 3.0
    EXTRACT_PROMPT = _PROMPT

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        url = f"https://www.xiaohongshu.com/search_result?keyword={query.replace(' ', '+')}&source=web_search_result_notes"
        return await self.scrape_url(url, query)
