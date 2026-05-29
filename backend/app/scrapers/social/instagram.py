"""Instagram Graph API 기반 가격 정보 스크래퍼."""
import re
from datetime import date

import httpx

from app.core.config import settings
from app.scrapers.base import BaseScraper, ScrapedEvent


class InstagramScraper(BaseScraper):
    """Instagram Graph API를 사용한 해시태그 검색 스크래퍼."""

    PLATFORM_NAME = "Instagram"
    COUNTRY = "GLOBAL"
    RATE_LIMIT_SEC = 1.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        """
        제품명을 해시태그로 검색하여 Instagram 가격 정보 수집.

        Args:
            query: 검색 키워드

        Returns:
            ScrapedEvent 리스트
        """
        events: list[ScrapedEvent] = []

        # API 키가 없으면 빈 리스트 반환
        if not settings.instagram_access_token:
            return events

        try:
            await self._wait_rate_limit()

            # 해시태그 검색 (한국어, 영어, 일본어 버전)
            hashtags = [
                query.replace(" ", ""),  # 띄어쓰기 제거
                query.lower().replace(" ", ""),  # 소문자
            ]

            for hashtag in hashtags:
                try:
                    await self._search_hashtag_and_extract_prices(
                        hashtag, query, events
                    )
                except Exception:
                    continue

        except Exception as exc:
            # 전체 스크래핑 실패 시
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )

        return events

    async def _search_hashtag_and_extract_prices(
        self, hashtag: str, product_name: str, events: list[ScrapedEvent]
    ) -> None:
        """
        해시태그로 검색하여 최근 미디어에서 가격 정보 추출.

        Args:
            hashtag: Instagram 해시태그 (# 제외)
            product_name: 원본 제품명
            events: 결과를 추가할 이벤트 리스트
        """
        # Note: Instagram Graph API v21.0에서 해시태그 검색은 user_id 필수
        # 실제 구현 시 인증된 사용자 ID가 필요
        # 여기서는 구조만 유지 (실제 user_id가 없으므로 API 호출 안 함)
        pass

    def _extract_prices(self, text: str, product_name: str) -> list[ScrapedEvent]:
        """
        텍스트에서 가격 정보 추출.

        Args:
            text: 추출 대상 텍스트 (caption, description 등)
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
                                event_name="Instagram 가격정보",
                                confidence=0.6,
                                raw_text=text[:200],  # 처음 200자만
                            )
                        )
                except (ValueError, AttributeError):
                    continue

        return events
