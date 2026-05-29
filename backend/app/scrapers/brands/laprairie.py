# La Prairie 글로벌 공식몰(laprairie.com) 한국 스토어 스크래퍼
from app.scrapers.firecrawl_base import FirecrawlBaseScraper


class LaPrairieScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "La Prairie Official"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 3.0
    PROMO_URL = "https://www.laprairie.com/en-kr/collections/luxury-skincare"
    EXTRACT_PROMPT = (
        "Extract all La Prairie skincare products on this page. "
        "Include product name, brand (La Prairie), sale price or regular price, currency (KRW or USD). "
        "If a product shows both regular and sale price, calculate discount rate. "
        "Set event_name to 'La Prairie' if no specific event name is shown."
    )
