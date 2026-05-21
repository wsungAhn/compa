"""Rakuten Japan scraper — Rakuten Ichiba Item Search API 기반."""
from datetime import date

import httpx

from app.core.config import settings
from app.scrapers.base import BaseScraper, ScrapedEvent


class RakutenScraper(BaseScraper):
    """Rakuten Ichiba Item Search API를 사용한 스크래퍼."""

    PLATFORM_NAME = "Rakuten"
    COUNTRY = "JP"
    RATE_LIMIT_SEC = 0.5

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        """
        제품명으로 Rakuten Ichiba 검색.

        Args:
            query: 검색 키워드

        Returns:
            ScrapedEvent 리스트 (최대 10개)
        """
        events: list[ScrapedEvent] = []

        # API 키가 없으면 빈 리스트 반환
        if not settings.rakuten_app_id:
            return events

        try:
            await self._wait_rate_limit()

            endpoint = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
            params = {
                "applicationId": settings.rakuten_app_id,
                "keyword": query,
                "format": "json",
                "hits": 10,
                "sort": "+itemPrice",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()

            data = response.json()

            # Items 배열 파싱
            items = data.get("Items", [])
            for item_wrapper in items:
                try:
                    item = item_wrapper.get("Item", {})

                    product_name = item.get("itemName", query)
                    sale_price_jpy = item.get("itemPrice")
                    source_url = item.get("itemUrl", "")

                    # itemPrice는 정수 → float 변환
                    sale_price = float(sale_price_jpy) if sale_price_jpy else None

                    raw_text = item.get("itemCaption", "")

                    if sale_price:
                        events.append(
                            ScrapedEvent(
                                product_name=product_name,
                                brand=None,
                                original_price=None,
                                sale_price=sale_price,
                                discount_rate=None,
                                currency="JPY",
                                start_date=date.today(),
                                end_date=None,
                                event_name="Rakuten 현재가",
                                reason=None,
                                source_url=source_url,
                                confidence=0.95,
                                raw_text=raw_text,
                            )
                        )
                except (KeyError, ValueError, TypeError):
                    # 개별 아이템 파싱 실패 시 계속 진행
                    continue

        except Exception as exc:
            # 전체 API 호출 실패 시
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )

        return events
