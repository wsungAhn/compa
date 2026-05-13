import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapedEvent

_SEARCH_URL = "https://www.amazon.com/s?k={query}&i=beauty"
_PRICE_RE = re.compile(r"[\d,]+")


def _parse_price(whole: str, fraction: str = "00") -> float | None:
    w = whole.strip().replace(",", "")
    f = fraction.strip()
    if not w.isdigit():
        return None
    return float(f"{w}.{f}")


class AmazonScraper(BaseScraper):
    PLATFORM_NAME = "Amazon US"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 2.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        try:
            await self._wait_rate_limit()
            url = _SEARCH_URL.format(query=query.replace(" ", "+"))
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                html = resp.text

            soup = BeautifulSoup(html, "html.parser")
            results = soup.select('div[data-component-type="s-search-result"]')

            for item in results[:5]:
                try:
                    name_el = item.select_one("h2 a span")
                    name = name_el.get_text(strip=True) if name_el else query

                    whole_el = item.select_one("span.a-price-whole")
                    frac_el = item.select_one("span.a-price-fraction")
                    if not whole_el:
                        continue
                    sale_price = _parse_price(
                        whole_el.get_text(strip=True).rstrip("."),
                        frac_el.get_text(strip=True) if frac_el else "00",
                    )
                    if not sale_price:
                        continue

                    orig_el = item.select_one("span.a-text-price span.a-offscreen")
                    original_price: float | None = None
                    if orig_el:
                        m = _PRICE_RE.search(orig_el.get_text(strip=True).replace(",", ""))
                        original_price = float(m.group()) if m else None

                    discount_rate: float | None = None
                    if original_price and sale_price and original_price > 0:
                        discount_rate = round((1 - sale_price / original_price) * 100, 1)

                    link_el = item.select_one("h2 a")
                    href = link_el.get("href", "") if link_el else ""
                    source_url = f"https://www.amazon.com{href}" if href.startswith("/") else url

                    events.append(
                        ScrapedEvent(
                            product_name=name,
                            original_price=original_price,
                            sale_price=sale_price,
                            discount_rate=discount_rate if discount_rate and discount_rate > 0 else None,
                            currency="USD",
                            event_name="Amazon 현재가",
                            source_url=source_url,
                            confidence=0.8,
                            raw_text=item.get_text(strip=True)[:300],
                        )
                    )
                except Exception:
                    continue

        except Exception as exc:
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )
        return events
