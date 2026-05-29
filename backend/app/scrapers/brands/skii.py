# SK-II 공식몰(sk-ii.com) Value & Gift Sets 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all SK-II products listed on this page with their prices. "
    "Include product name, original price, sale price if discounted, currency (USD). "
    "Set event_name to 'SK-II Value & Gift Sets'."
)


class SKIIScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "SK-II Official"
    COUNTRY = "GLOBAL"
    RATE_LIMIT_SEC = 2.0
    PROMO_URL = "https://www.sk-ii.com/our-products/category/value-gift-sets"
    EXTRACT_PROMPT = _PROMPT
