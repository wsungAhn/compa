import re
from datetime import date

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapedEvent

SEARCH_URL = "https://www.coupang.com/np/search?q={query}&channel=user&from=pc"

_PRICE_RE = re.compile(r"[\d,]+")


def _parse_price(text: str) -> float | None:
    """문자열에서 숫자를 추출하여 float으로 변환."""
    if not text:
        return None
    text_clean = text.replace(",", "").strip()
    m = _PRICE_RE.search(text_clean)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None


class CoupangScraper(BaseScraper):
    PLATFORM_NAME = "쿠팡"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 1.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        """쿠팡에서 제품명으로 할인 행사 데이터를 수집."""
        events: list[ScrapedEvent] = []
        try:
            await self._wait_rate_limit()

            url = SEARCH_URL.format(query=query)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            # 쿠팡 검색 결과 상품 선택자
            # 일반적으로 상품 항목은 div.search-product 또는 li.search-item 형태
            items = soup.select("div.search-product")
            if not items:
                items = soup.select("li.search-item")

            for item in items[:5]:  # 최대 5개 상품
                try:
                    # 상품명 파싱
                    name_el = item.select_one(".name")
                    if not name_el:
                        name_el = item.select_one("a.product-name")
                    product_name = name_el.get_text(strip=True) if name_el else query

                    # 현재 가격 파싱
                    price_el = item.select_one(".price-value")
                    if not price_el:
                        price_el = item.select_one("strong.price")
                    sale_price_text = price_el.get_text(strip=True) if price_el else ""
                    sale_price = _parse_price(sale_price_text)

                    # 할인 전 가격 파싱 (del 태그 또는 .base-price)
                    original_el = item.select_one("del")
                    if not original_el:
                        original_el = item.select_one(".base-price")
                    original_price_text = original_el.get_text(strip=True) if original_el else ""
                    original_price = _parse_price(original_price_text)

                    # 할인율 계산
                    discount_rate: float | None = None
                    if original_price and sale_price and original_price > 0:
                        discount_rate = round((1 - sale_price / original_price) * 100, 1)

                    # raw_text 저장
                    raw_text = item.get_text(strip=True)

                    # 할인 상품만 추가 (sale_price < original_price)
                    if sale_price and original_price and sale_price < original_price:
                        events.append(
                            ScrapedEvent(
                                product_name=product_name,
                                original_price=original_price,
                                sale_price=sale_price,
                                discount_rate=discount_rate,
                                currency="KRW",
                                event_name="쿠팡 할인",
                                source_url=url,
                                confidence=0.85,
                                raw_text=raw_text,
                            )
                        )
                except Exception:
                    # 개별 상품 파싱 실패 시 스킵 (예외 전파 금지)
                    pass

        except Exception as exc:
            # 전체 실패 시 confidence=0.0으로 반환
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )

        return events
