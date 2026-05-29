# firecrawl-local을 통해 페이지를 수집하는 스크래퍼 베이스
import logging
from datetime import date

from app.scrapers.base import BaseScraper, ScrapedEvent
from app.scrapers.firecrawl_client import firecrawl_scrape

_logger = logging.getLogger(__name__)


class FirecrawlBaseScraper(BaseScraper):
    """firecrawl-local API 기반 스크래퍼.

    서브클래스는 PROMO_URL, EXTRACT_PROMPT만 정의하면 됨.
    """

    PROMO_URL: str = ""
    EXTRACT_PROMPT: str = (
        "Extract all discounted or on-sale cosmetics products with their prices."
    )
    WAIT_FOR: str | None = None
    REMOVE_SELECTORS: list[str] = []
    RATE_LIMIT_SEC: float = 2.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        await self._wait_rate_limit()

        raw_products = await firecrawl_scrape(
            url=self.PROMO_URL,
            extract_prompt=self.EXTRACT_PROMPT,
            wait_for=self.WAIT_FOR,
            remove_selectors=self.REMOVE_SELECTORS,
        )

        return self._parse_products(raw_products, query, self.PROMO_URL)

    async def scrape_url(
        self, url: str, query: str, prompt: str | None = None
    ) -> list[ScrapedEvent]:
        """동적 URL로 스크래핑. scrape() 오버라이드용."""
        await self._wait_rate_limit()

        products = await firecrawl_scrape(
            url=url,
            extract_prompt=prompt or self.EXTRACT_PROMPT,
            wait_for=self.WAIT_FOR,
            remove_selectors=self.REMOVE_SELECTORS,
        )
        return self._parse_products(products, query, url)

    def _parse_products(
        self, products: list[dict], query: str, source_url: str
    ) -> list[ScrapedEvent]:
        """raw products dict → ScrapedEvent 리스트. query 필터 포함."""
        events: list[ScrapedEvent] = []
        for p in products:
            try:
                # query 필터: query가 있으면 product_name에 포함 여부 체크 (대소문자 무시)
                name = p.get("product_name", "")
                if query and query.lower() not in name.lower():
                    # 브랜드명도 확인
                    brand = p.get("brand") or ""
                    if query.lower() not in brand.lower():
                        continue

                # 날짜 파싱
                def parse_date(v: object) -> date | None:
                    if not v or not isinstance(v, str):
                        return None
                    try:
                        return date.fromisoformat(v)
                    except ValueError:
                        return None

                events.append(
                    ScrapedEvent(
                        product_name=name,
                        brand=p.get("brand"),
                        original_price=p.get("original_price"),
                        sale_price=p.get("sale_price"),
                        discount_rate=p.get("discount_rate"),
                        currency=p.get("currency"),
                        start_date=parse_date(p.get("start_date")),
                        end_date=parse_date(p.get("end_date")),
                        event_name=p.get("event_name"),
                        reason=p.get("reason"),
                        source_url=source_url,
                        confidence=float(p.get("confidence", 0.8)),
                    )
                )
            except Exception as exc:
                _logger.warning(
                    f"{self.PLATFORM_NAME} product parse error: {exc}"
                )
                continue

        return events
