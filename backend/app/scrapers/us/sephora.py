"""Sephora US scraper — Playwright 기반."""
import re
from datetime import date

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper, ScrapedEvent

SEARCH_URL = "https://www.sephora.com/search?keyword={query}"
SALE_URL = "https://www.sephora.com/sale"

_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


def _parse_usd(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    return float(m.group(1).replace(",", "")) if m else None


class SephoraScraper(BaseScraper):
    PLATFORM_NAME = "Sephora"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 1.5

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                )
                page = await context.new_page()
                await self._wait_rate_limit()

                url = SEARCH_URL.format(query=query.replace(" ", "+"))
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2500)

                # 상품 카드 파싱
                cards = await page.query_selector_all('[data-comp="ProductGrid"] [data-comp="ProductCard"]')
                if not cards:
                    cards = await page.query_selector_all('.css-ix8km1')

                for card in cards[:8]:
                    try:
                        name_el = await card.query_selector('[data-comp="DisplayName"]')
                        if not name_el:
                            name_el = await card.query_selector('.css-0')
                        name = (await name_el.inner_text()).strip() if name_el else query

                        brand_el = await card.query_selector('[data-comp="BrandName"]')
                        brand = (await brand_el.inner_text()).strip() if brand_el else None

                        # 현재가
                        price_el = await card.query_selector('[data-comp="Price"]')
                        price_text = (await price_el.inner_text()) if price_el else ""
                        prices = _PRICE_RE.findall(price_text)

                        sale_price: float | None = None
                        original_price: float | None = None
                        discount_rate: float | None = None

                        if len(prices) >= 2:
                            original_price = float(prices[0].replace(",", ""))
                            sale_price = float(prices[1].replace(",", ""))
                            discount_rate = round((1 - sale_price / original_price) * 100, 1)
                        elif len(prices) == 1:
                            sale_price = float(prices[0].replace(",", ""))

                        raw_text = await card.inner_text()
                        link_el = await card.query_selector("a")
                        href = await link_el.get_attribute("href") if link_el else ""
                        source_url = f"https://www.sephora.com{href}" if href else url

                        # 세일 중인 경우만 이벤트로 저장 (둘 다 가격 있는 경우)
                        if sale_price and (original_price or discount_rate):
                            events.append(ScrapedEvent(
                                product_name=name,
                                brand=brand,
                                original_price=original_price,
                                sale_price=sale_price,
                                discount_rate=discount_rate,
                                currency="USD",
                                event_name="Sephora Sale",
                                source_url=source_url,
                                confidence=0.85,
                                raw_text=raw_text,
                            ))
                        elif sale_price:
                            # 현재가만 있어도 저장 (비교용)
                            events.append(ScrapedEvent(
                                product_name=name,
                                brand=brand,
                                sale_price=sale_price,
                                currency="USD",
                                event_name="Sephora 현재가",
                                source_url=source_url,
                                confidence=0.9,
                                raw_text=raw_text,
                            ))
                    except Exception:
                        continue

                # Sephora 세일 페이지 별도 수집
                await self._wait_rate_limit()
                try:
                    events += await self._scrape_sale_page(page, query)
                except Exception:
                    pass

                await browser.close()
        except Exception as exc:
            events.append(ScrapedEvent(
                product_name=query,
                confidence=0.0,
                raw_text=str(exc),
            ))
        return events

    async def _scrape_sale_page(self, page, query: str) -> list[ScrapedEvent]:  # type: ignore[no-untyped-def]
        events: list[ScrapedEvent] = []
        await page.goto(SALE_URL, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)

        # 세일 배너/이벤트 정보 수집
        banners = await page.query_selector_all('[data-comp="Promo"], .css-1qe8tjm, [class*="promo"]')
        for banner in banners[:5]:
            try:
                text = (await banner.inner_text()).strip()
                if not text or len(text) < 5:
                    continue

                # 할인율 파싱
                rate_m = re.search(r"(\d+)%\s*off", text, re.IGNORECASE)
                discount_rate = float(rate_m.group(1)) if rate_m else None

                # 날짜 파싱
                date_m = re.search(r"(?:through|until|ends?)\s+(\w+\.?\s+\d+)", text, re.IGNORECASE)
                end_date: date | None = None
                if date_m:
                    try:
                        from datetime import datetime
                        end_date = datetime.strptime(date_m.group(1).strip("."), "%b %d").replace(
                            year=date.today().year
                        ).date()
                    except ValueError:
                        pass

                if discount_rate:
                    events.append(ScrapedEvent(
                        product_name=query,
                        discount_rate=discount_rate,
                        currency="USD",
                        end_date=end_date,
                        event_name="Sephora Sale Event",
                        source_url=SALE_URL,
                        confidence=0.65,
                        raw_text=text,
                    ))
            except Exception:
                continue
        return events
