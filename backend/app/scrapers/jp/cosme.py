import re

import httpx
from bs4 import BeautifulSoup

from app.core.proxy import httpx_proxy
from app.scrapers.base import BaseScraper, ScrapedEvent

_SEARCH_URL = "https://www.cosme.com/products/list.php?keyword={query}"
_JPY_RE = re.compile(r"([\d,]+)\s*円|¥\s*([\d,]+)")


def _parse_jpy(text: str) -> float | None:
    """Parse JPY price from text like '¥3000' or '3,000円'."""
    m = _JPY_RE.search(str(text))
    if m:
        price_str = m.group(1) or m.group(2)
        return float(price_str.replace(",", ""))
    return None


def parse_search_html(html: str, url: str) -> list[ScrapedEvent]:
    """Parse @cosme search HTML and extract product events.

    Args:
        html: HTML content from search page
        url: Source URL for the search

    Returns:
        List of ScrapedEvent objects extracted from the HTML
    """
    events: list[ScrapedEvent] = []
    soup = BeautifulSoup(html, "html.parser")

    # Defensive: try multiple selectors for product list items
    product_items = (
        soup.select("li.item")
        or soup.select("div.product-item")
        or soup.select("li[class*='item']")
        or soup.select("div[class*='product']")
    )

    for item in product_items[:5]:
        try:
            # Extract product name: try multiple selectors
            name_el = (
                item.select_one("a.product-name")
                or item.select_one("a[class*='name']")
                or item.select_one("a")
            )
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Extract price: look for yen currency indicators
            # Try multiple price selectors
            price_text: str | None = None
            price_el = (
                item.select_one("span[class*='price']")
                or item.select_one("div[class*='price']")
                or item.select_one("p[class*='price']")
            )
            if price_el:
                price_text = price_el.get_text(strip=True)
            else:
                # Fallback: search item text for yen currency
                price_text = item.get_text(strip=True)

            if not price_text:
                continue

            sale_price = _parse_jpy(price_text)
            if not sale_price:
                continue

            # @cosme shopping site typically shows current prices only
            # Original price info is less commonly available in HTML
            original_price: float | None = None

            events.append(
                ScrapedEvent(
                    product_name=name,
                    original_price=original_price,
                    sale_price=sale_price,
                    discount_rate=None,
                    currency="JPY",
                    event_name="@cosme 現在価格",
                    source_url=url,
                    confidence=0.75,
                    raw_text=item.get_text(strip=True)[:300],
                )
            )
        except Exception:
            continue

    return events


class CosmeScraper(BaseScraper):
    PLATFORM_NAME = "@cosme"
    COUNTRY = "JP"
    RATE_LIMIT_SEC = 1.5

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
                "Accept-Language": "ja-JP,ja;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            proxy = httpx_proxy()

            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, proxy=proxy
            ) as client:
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
