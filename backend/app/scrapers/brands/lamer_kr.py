# La Mer 한국 공식몰(lamerkorea.com) 오퍼 페이지 스크래퍼
from app.scrapers.firecrawl_base import FirecrawlBaseScraper


class LaMerKRScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "La Mer Official KR"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 3.0
    PROMO_URL = "https://www.lamerkorea.com/offers"
    EXTRACT_PROMPT = (
        "Extract all La Mer skincare products on this offers or promotions page. "
        "Include product name, original price, sale price if discounted, discount rate, currency (KRW). "
        "Set event_name to 'La Mer Offers'."
    )
