# Chantecaille 한국 공식몰(chantecaille.kr) 세일 컬렉션 스크래퍼
from app.scrapers.firecrawl_base import FirecrawlBaseScraper


class ChantecailleKRScraper(FirecrawlBaseScraper):
    PLATFORM_NAME = "Chantecaille Official KR"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 3.0
    PROMO_URL = "https://chantecaille.kr/collections/sale"
    EXTRACT_PROMPT = (
        "Extract all Chantecaille products listed on this sale collection page. "
        "Include product name, original price, sale price, discount rate, currency (KRW). "
        "Set event_name to 'Chantecaille Sale'."
    )
