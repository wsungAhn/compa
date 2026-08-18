from datetime import date
from typing import Any

import httpx

from app.core.config import settings
from app.core.size import unambiguous_size_ml
from app.scrapers.base import BaseScraper, ScrapedEvent

# 2026 API. The 2017 endpoint (app.rakuten.co.jp) is retired and rejects the
# UUID-style applicationId the developer portal now issues.
_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
# Rakuten rejects the request with REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING
# unless it matches an "Allowed website" registered for the application.
_REFERER = "https://wsungahn.github.io"


def parse_response(data: dict[str, Any], query: str) -> list[ScrapedEvent]:
    """Parse Rakuten API response and extract product events.

    Args:
        data: JSON response dict from Rakuten API
        query: Original search query

    Returns:
        List of ScrapedEvent objects extracted from the response
    """
    events: list[ScrapedEvent] = []
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
                    size_ml=unambiguous_size_ml(item.get("itemName", "")),
                    sale_price=sale_price,
                    currency="JPY",
                    start_date=date.today(),
                    event_name="Rakuten 현재가",
                    source_url=item.get("itemUrl", ""),
                    confidence=0.95,
                    raw_text=item.get("itemCaption", ""),
                    external_id=item.get("itemCode"),
                    id_type="item_code",
                )
            )
        except Exception:
            continue
    return events


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
            params: dict[str, str | int] = {
                "applicationId": settings.rakuten_app_id,
                "keyword": query,
                "format": "json",
                "hits": 10,
                "sort": "+itemPrice",
            }
            if settings.rakuten_access_key:
                params["accessKey"] = settings.rakuten_access_key
            headers = {"Referer": _REFERER, "Origin": _REFERER}
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(_ENDPOINT, params=params, headers=headers)
                resp.raise_for_status()
            data = resp.json()
            events = parse_response(data, query)
        except Exception as exc:
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )
        return events
