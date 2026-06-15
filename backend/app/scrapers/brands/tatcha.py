# Tatcha 공식몰(tatcha.com) 신제품/세일 스크래퍼
from app.scrapers.firecrawl_base import FirecrawlBaseScraper


class TatchaScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Tatcha Official"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 3.0
    PROMO_URL = "https://tatcha.com/collections/new"
    EXTRACT_PROMPT = (
        "Extract all Tatcha skincare products on this page. "
        "Include product name, original price, sale price if discounted, currency (USD). "
        "If a product is on sale or has a special offer, include the discount rate."
    )
