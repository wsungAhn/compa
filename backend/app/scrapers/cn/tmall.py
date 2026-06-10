import re

import httpx
from bs4 import BeautifulSoup

from app.core.proxy import httpx_proxy
from app.scrapers.base import BaseScraper, ScrapedEvent

_SEARCH_URL = "https://list.tmall.com/search_product.htm?q={query}"
_CNY_RE = re.compile(r"¥?\s*([\d,]+(?:\.\d+)?)")


def _parse_cny(text: str) -> float | None:
    """Parse CNY price from text like '¥29.99' or '29.99'."""
    if not text:
        return None
    text_clean = text.strip()
    m = _CNY_RE.search(text_clean)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def parse_search_html(html: str, url: str) -> list[ScrapedEvent]:
    """Parse Tmall search HTML and extract product events.

    Args:
        html: HTML content from search page
        url: Source URL for the search

    Returns:
        List of ScrapedEvent objects extracted from the HTML
    """
    events: list[ScrapedEvent] = []
    soup = BeautifulSoup(html, "html.parser")

    # Defensive: try multiple selectors for product items
    items = (
        soup.select("div.product")
        or soup.select("div[class*='product-item']")
        or soup.select("div.J_TItems")
        or soup.select("div[data-id]")
    )

    for item in items[:5]:
        try:
            # Extract product name: try multiple selectors
            name_el = item.select_one(".productTitle a") or item.select_one("a[title]")
            product_name = ""
            if name_el:
                # Prefer title attribute, fallback to text
                title_attr = name_el.get("title")
                if isinstance(title_attr, str):
                    product_name = title_attr
                else:
                    product_name_text = name_el.get_text(strip=True)
                    if isinstance(product_name_text, str):
                        product_name = product_name_text

            if not product_name:
                continue

            # Extract price: try multiple selectors
            price_el = item.select_one(".productPrice em") or item.select_one(
                "[class*='price']"
            )

            if not price_el:
                continue

            # Try to get price from title attribute first (common pattern)
            price_attr = price_el.get("title")
            if isinstance(price_attr, str):
                price_text = price_attr
            else:
                price_text_raw = price_el.get_text(strip=True)
                price_text = price_text_raw if isinstance(price_text_raw, str) else ""
            sale_price = _parse_cny(price_text)

            if not sale_price:
                continue

            # For Tmall, usually we only get current price, not original
            # But check for any discount indicators
            raw_text = item.get_text(strip=True)

            events.append(
                ScrapedEvent(
                    product_name=product_name,
                    sale_price=sale_price,
                    original_price=None,
                    discount_rate=None,
                    currency="CNY",
                    event_name="Tmall 现价",
                    source_url=url,
                    confidence=0.7,
                    raw_text=raw_text[:500] if raw_text else None,
                )
            )
        except Exception:
            continue

    return events


class TmallScraper(BaseScraper):
    PLATFORM_NAME = "Tmall"
    COUNTRY = "CN"
    RATE_LIMIT_SEC = 2.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        try:
            await self._wait_rate_limit()

            url = _SEARCH_URL.format(query=query)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            proxy = httpx_proxy()

            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, proxy=proxy
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                html = response.text

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
