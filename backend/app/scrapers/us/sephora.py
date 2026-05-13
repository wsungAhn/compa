import re
from typing import Any

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper, ScrapedEvent

SEARCH_URL = "https://www.sephora.com/search?keyword={query}"

_PRICE_RE = re.compile(r"\$([\d,.]+)")


def _parse_usd(text: str) -> float | None:
    m = _PRICE_RE.search(str(text))
    return float(m.group(1).replace(",", "")) if m else None


def _min_price(list_price: str) -> float | None:
    """'$20.00 - $32.00' 형태에서 최솟값 반환."""
    prices = _PRICE_RE.findall(list_price)
    if not prices:
        return None
    return min(float(p.replace(",", "")) for p in prices)


class SephoraScraper(BaseScraper):
    PLATFORM_NAME = "Sephora"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 1.5

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    executable_path="/usr/bin/google-chrome-stable",
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                )
                page = await context.new_page()

                api_data: dict[str, Any] = {}

                async def handle_response(resp: Any) -> None:
                    if "/api/v2/catalog/search/" in resp.url and resp.status == 200:
                        try:
                            body = await resp.json()
                            api_data["products"] = body.get("products", [])
                        except Exception:
                            pass

                page.on("response", handle_response)

                await self._wait_rate_limit()
                url = SEARCH_URL.format(query=query.replace(" ", "+"))
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(8000)
                await browser.close()

            for product in api_data.get("products", [])[:10]:
                try:
                    name = product.get("displayName", query)
                    brand = product.get("brandName")
                    sku = product.get("currentSku", {})
                    list_price = sku.get("listPrice", "")
                    sale_price = _min_price(list_price)
                    if not sale_price:
                        continue
                    product_url = product.get("targetUrl") or product.get("url", "")
                    source_url = f"https://www.sephora.com{product_url}" if product_url else url
                    events.append(
                        ScrapedEvent(
                            product_name=name,
                            brand=brand,
                            sale_price=sale_price,
                            currency="USD",
                            event_name="Sephora 현재가",
                            source_url=source_url,
                            confidence=0.9,
                            raw_text=list_price,
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
