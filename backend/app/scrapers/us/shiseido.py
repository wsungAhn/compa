# Shiseido 미국 공식몰(shiseido.com) Exclusive Offers 스크래퍼
from app.scrapers.base import ScrapedEvent
from app.scrapers.firecrawl_base import FirecrawlBaseScraper

_PROMPT = (
    "Extract all Shiseido products on this exclusive offers or promotions page. "
    "Include product name, original price (standard price), sale price (promotional price), "
    "discount rate if available, currency (USD). "
    "Set event_name to 'Shiseido Exclusive Offers'."
)


class ShiseidoScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Shiseido Official"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 2.0
    PROMO_URL = "https://www.shiseido.com/us/en/exclusive-online-offers.html"
    EXTRACT_PROMPT = _PROMPT
    WAIT_FOR = ".product-tile"
