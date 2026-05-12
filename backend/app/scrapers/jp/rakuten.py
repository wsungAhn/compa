"""Rakuten Japan scraper — Playwright 기반 (API 없이)."""
import re

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper, ScrapedEvent

SEARCH_URL = "https://search.rakuten.co.jp/search/mall/{query}/?l-id=s_search&f=1&p=1&s=6"

_PRICE_RE = re.compile(r"([\d,]+)\s*円")


def _parse_jpy(text: str) -> float | None:
    m = _PRICE_RE.search(text.replace(",", ""))
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


class RakutenScraper(BaseScraper):
    PLATFORM_NAME = "Rakuten"
    COUNTRY = "JP"
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
                    locale="ja-JP",
                    extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9"},
                )
                page = await context.new_page()
                await self._wait_rate_limit()

                url = SEARCH_URL.format(query=query.replace(" ", "+"))
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                cards = await page.query_selector_all(".searchresultitem")
                if not cards:
                    cards = await page.query_selector_all('[data-testid="item-container"]')

                for card in cards[:8]:
                    try:
                        name_el = await card.query_selector(".content.title a")
                        if not name_el:
                            name_el = await card.query_selector("h2 a, .item_name a")
                        name = (await name_el.inner_text()).strip() if name_el else query

                        # 현재가
                        price_el = await card.query_selector(".important")
                        if not price_el:
                            price_el = await card.query_selector(".price")
                        price_text = (await price_el.inner_text()) if price_el else ""
                        sale_price = _parse_jpy(price_text)

                        # 정가 (있는 경우)
                        original_el = await card.query_selector(".before")
                        original_text = (await original_el.inner_text()) if original_el else ""
                        original_price = _parse_jpy(original_text)

                        discount_rate: float | None = None
                        if sale_price and original_price and original_price > sale_price:
                            discount_rate = round((1 - sale_price / original_price) * 100, 1)

                        # 할인율 배지
                        off_el = await card.query_selector(".off")
                        off_text = (await off_el.inner_text()).strip() if off_el else ""
                        if not discount_rate and off_text:
                            m = re.search(r"(\d+)%", off_text)
                            if m:
                                discount_rate = float(m.group(1))

                        link_el = await card.query_selector("a")
                        source_url = await link_el.get_attribute("href") if link_el else url

                        raw_text = await card.inner_text()

                        if sale_price:
                            events.append(ScrapedEvent(
                                product_name=name,
                                brand=None,
                                original_price=original_price,
                                sale_price=sale_price,
                                discount_rate=discount_rate,
                                currency="JPY",
                                event_name="楽天セール" if discount_rate else "楽天 現在価格",
                                source_url=source_url or url,
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
