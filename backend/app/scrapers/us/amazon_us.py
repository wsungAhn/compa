"""Amazon US scraper — Playwright 기반 (PA API 없이)."""
import re

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper, ScrapedEvent

SEARCH_URL = "https://www.amazon.com/s?k={query}&i=beauty"

_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")


def _parse_usd(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    return float(m.group(1).replace(",", "")) if m else None


class AmazonUSScraper(BaseScraper):
    PLATFORM_NAME = "Amazon US"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 2.0

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
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                )
                page = await context.new_page()
                await self._wait_rate_limit()

                url = SEARCH_URL.format(query=query.replace(" ", "+"))
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                cards = await page.query_selector_all('[data-component-type="s-search-result"]')

                for card in cards[:8]:
                    try:
                        name_el = await card.query_selector("h2 span")
                        name = (await name_el.inner_text()).strip() if name_el else query

                        brand_el = await card.query_selector(".a-size-base-plus")
                        brand = (await brand_el.inner_text()).strip() if brand_el else None

                        # 현재가
                        price_whole = await card.query_selector(".a-price-whole")
                        price_frac = await card.query_selector(".a-price-fraction")
                        sale_price: float | None = None
                        if price_whole:
                            whole = (await price_whole.inner_text()).replace(",", "").strip(".")
                            frac = (await price_frac.inner_text()).strip() if price_frac else "00"
                            try:
                                sale_price = float(f"{whole}.{frac}")
                            except ValueError:
                                pass

                        # 정가 (있는 경우)
                        original_el = await card.query_selector(".a-text-price span")
                        original_text = (await original_el.inner_text()) if original_el else ""
                        original_price = _parse_usd(original_text)

                        discount_rate: float | None = None
                        if sale_price and original_price and original_price > sale_price:
                            discount_rate = round((1 - sale_price / original_price) * 100, 1)

                        # 배지 (할인 표시)
                        badge_el = await card.query_selector(".a-badge-text")
                        badge_text = (await badge_el.inner_text()).strip() if badge_el else ""
                        if not discount_rate:
                            m = re.search(r"(\d+)%\s*off", badge_text, re.IGNORECASE)
                            if m:
                                discount_rate = float(m.group(1))

                        link_el = await card.query_selector("h2 a")
                        href = await link_el.get_attribute("href") if link_el else ""
                        source_url = f"https://www.amazon.com{href}" if href and href.startswith("/") else url

                        raw_text = await card.inner_text()

                        if sale_price:
                            events.append(ScrapedEvent(
                                product_name=name,
                                brand=brand,
                                original_price=original_price,
                                sale_price=sale_price,
                                discount_rate=discount_rate,
                                currency="USD",
                                event_name="Amazon Sale" if discount_rate else "Amazon 현재가",
                                source_url=source_url,
                                confidence=0.85,
                                raw_text=raw_text,
                            ))
                    except Exception:
                        continue

                await browser.close()
        except Exception as exc:
            events.append(ScrapedEvent(
                product_name=query,
                confidence=0.0,
                raw_text=str(exc),
            ))
        return events
