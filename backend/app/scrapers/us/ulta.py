import re

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapedEvent

_SEARCH_URL = "https://www.ulta.com/shop/search?search={query}"
_USD_RE = re.compile(r"\$([\d,.]+)")


def _parse_usd(text: str) -> float | None:
    """Parse USD price from text like '$23.50'."""
    m = _USD_RE.search(str(text))
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def parse_search_html(html: str, url: str) -> list[ScrapedEvent]:
    """Parse Ulta search HTML and extract product events.

    Args:
        html: HTML content from search page
        url: Source URL for the search

    Returns:
        List of ScrapedEvent objects extracted from the HTML
    """
    events: list[ScrapedEvent] = []
    soup = BeautifulSoup(html, "html.parser")

    # Defensive: try multiple selectors for product cards
    product_cards = (
        soup.select('[data-test="product-card"]')
        or soup.select("div.ProductCard")
        or soup.select("div[class*='product-card']")
        or soup.select("li[class*='product']")
    )

    for item in product_cards[:5]:
        try:
            # Extract product name: try multiple selectors
            name_el = (
                item.select_one('[data-test="product-name"]')
                or item.select_one("a.ProductCard__name")
                or item.select_one("a[class*='product-name']")
                or item.select_one("a")
            )
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Extract current/sale price: try multiple selectors
            price_el = (
                item.select_one('[data-test="product-price"]')
                or item.select_one("span.ProductCard__price")
                or item.select_one("span[class*='sale-price']")
            )
            if not price_el:
                continue

            sale_price = _parse_usd(price_el.get_text(strip=True))
            if not sale_price:
                continue

            # Extract original/strikethrough price: try multiple selectors
            original_price: float | None = None
            orig_el = (
                item.select_one("s")
                or item.select_one("del")
                or item.select_one("span.ProductCard__originalPrice")
                or item.select_one("span[class*='original-price']")
            )
            if orig_el:
                original_price = _parse_usd(orig_el.get_text(strip=True))

            # Compute discount rate if both prices exist
            discount_rate: float | None = None
            if original_price and sale_price and original_price > 0:
                discount_rate = round((1 - sale_price / original_price) * 100, 1)

            # Determine event name based on discount
            event_name = "Ulta 할인" if (discount_rate and discount_rate > 0) else "Ulta 현재가"

            events.append(
                ScrapedEvent(
                    product_name=name,
                    original_price=original_price,
                    sale_price=sale_price,
                    discount_rate=discount_rate if discount_rate and discount_rate > 0 else None,
                    currency="USD",
                    event_name=event_name,
                    source_url=url,
                    confidence=0.8,
                    raw_text=item.get_text(strip=True)[:300],
                )
            )
        except Exception:
            continue

    return events


class UltaScraper(BaseScraper):
    PLATFORM_NAME = "Ulta"
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

            events = parse_search_html(html, url)

        except Exception as exc:
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )
        return events
