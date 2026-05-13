from datetime import date

import httpx

from app.core.config import settings
from app.scrapers.base import BaseScraper, ScrapedEvent

_ENDPOINT = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"


class RakutenScraper(BaseScraper):
    PLATFORM_NAME = "Rakuten"
    COUNTRY = "JP"
    RATE_LIMIT_SEC = 0.5

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        if not settings.rakuten_app_id:
            return events
        try:
            await self._wait_rate_limit()
            params = {
                "applicationId": settings.rakuten_app_id,
                "keyword": query,
                "format": "json",
                "hits": 10,
                "sort": "+itemPrice",
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(_ENDPOINT, params=params)
                resp.raise_for_status()
            data = resp.json()
            for wrapper in data.get("Items", []):
                try:
                    item = wrapper.get("Item", {})
                    price_raw = item.get("itemPrice")
                    sale_price = float(price_raw) if price_raw else None
                    if not sale_price:
                        continue
                    events.append(
                        ScrapedEvent(
                            product_name=item.get("itemName", query),
                            sale_price=sale_price,
                            currency="JPY",
                            start_date=date.today(),
                            event_name="Rakuten 현재가",
                            source_url=item.get("itemUrl", ""),
                            confidence=0.95,
                            raw_text=item.get("itemCaption", ""),
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
