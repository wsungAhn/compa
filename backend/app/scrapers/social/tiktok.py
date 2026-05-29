"""TikTok Research API 기반 가격 정보 스크래퍼."""
import json
import re
from datetime import date

import httpx

from app.core.config import settings
from app.scrapers.base import BaseScraper, ScrapedEvent


class TikTokScraper(BaseScraper):
    """TikTok Research API를 사용한 비디오 검색 스크래퍼."""

    PLATFORM_NAME = "TikTok"
    COUNTRY = "GLOBAL"
    RATE_LIMIT_SEC = 1.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        """
        제품명으로 TikTok 비디오 검색하여 가격 정보 수집.

        Args:
            query: 검색 키워드

        Returns:
            ScrapedEvent 리스트
        """
        events: list[ScrapedEvent] = []

        # API 키가 없으면 빈 리스트 반환
        if not settings.tiktok_client_key:
            return events

        try:
            await self._wait_rate_limit()

            endpoint = "https://open.tiktokapis.com/v2/research/video/query/"

            # TikTok Research API 요청 구조
            payload = {
                "query": {
                    "and": [
                        {
                            "operation": "EQ",
                            "field_name": "keyword",
                            "field_values": [query],
                        }
                    ]
                },
                "data_spec": {
                    "fields": ["video_description", "video_id", "create_time"]
                },
                "max_count": 10,
            }

            headers = {
                "Authorization": f"Bearer {settings.tiktok_client_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    endpoint, json=payload, headers=headers
                )
                response.raise_for_status()

            data = response.json()

            # videos 배열에서 가격 정보 추출
            videos = data.get("data", {}).get("videos", [])
            for video in videos:
                try:
                    description = video.get("video_description", "")
                    video_id = video.get("video_id", "")

                    if description:
                        # 가격 정보 추출
                        price_events = self._extract_prices(description, query)
                        for event in price_events:
                            event.source_url = (
                                f"https://www.tiktok.com/video/{video_id}"
                            )
                            events.append(event)
                except (KeyError, ValueError, TypeError):
                    # 개별 비디오 파싱 실패 시 계속 진행
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

    def _extract_prices(self, text: str, product_name: str) -> list[ScrapedEvent]:
        """
        텍스트에서 가격 정보 추출.

        Args:
            text: 추출 대상 텍스트 (video_description 등)
            product_name: 제품명

        Returns:
            ScrapedEvent 리스트
        """
        events: list[ScrapedEvent] = []

        # 정규식으로 가격 추출
        price_patterns = [
            (r"([\d,]+)원", "KRW"),  # 한국 원화
            (r"\$([\d,]+(?:\.\d{2})?)", "USD"),  # USD
            (r"([\d,]+)円", "JPY"),  # 일본 엔
            (r"([\d,]+)元", "CNY"),  # 중국 위안
        ]

        for pattern, currency in price_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    price_str = match.group(1).replace(",", "")
                    price = float(price_str)

                    if price > 0:
                        events.append(
                            ScrapedEvent(
                                product_name=product_name,
                                sale_price=price,
                                currency=currency,
                                start_date=date.today(),
                                event_name="TikTok 가격정보",
                                confidence=0.5,
                                raw_text=text[:200],  # 처음 200자만
                            )
                        )
                except (ValueError, AttributeError):
                    continue

        return events
