import asyncio
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from app.core.config import settings
from app.scrapers.base import BaseScraper, ScrapedEvent

SEARCH_API = "https://openapi.naver.com/v1/search/shop.json"
INSIGHT_API = "https://openapi.naver.com/v1/datalab/shopping/category/keywords"

# 올리브영 취급 주요 카테고리 (네이버쇼핑 코드)
BEAUTY_CATEGORIES = {
    "스킨케어": "50000803",
    "메이크업": "50000804",
    "클렌징": "50000805",
    "선케어": "50000806",
}


@dataclass
class NaverShopItem:
    title: str
    brand: str | None
    lprice: int  # 최저가 (원)
    hprice: int  # 최고가 (원)
    mall_name: str
    product_id: str
    product_url: str
    category: str | None


class NaverShopScraper(BaseScraper):
    PLATFORM_NAME = "네이버쇼핑"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 0.5

    def __init__(self) -> None:
        super().__init__()
        self._headers = {
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
        }

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        try:
            items = await self._search_products(query)
            for item in items[:10]:
                clean_title = item.title.replace("<b>", "").replace("</b>", "")
                events.append(
                    ScrapedEvent(
                        product_name=clean_title,
                        brand=item.brand,
                        sale_price=float(item.lprice) if item.lprice else None,
                        original_price=float(item.hprice) if item.hprice else None,
                        currency="KRW",
                        event_name="네이버쇼핑 최저가",
                        source_url=item.product_url,
                        confidence=0.9,
                        raw_text=f"{clean_title} | 최저가: {item.lprice}원",
                    )
                )
        except Exception as exc:
            events.append(ScrapedEvent(product_name=query, confidence=0.0, raw_text=str(exc)))
        return events

    async def _search_products(self, query: str, display: int = 20) -> list[NaverShopItem]:
        await self._wait_rate_limit()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                SEARCH_API,
                headers=self._headers,
                params={"query": query, "display": display, "sort": "sim"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            NaverShopItem(
                title=item.get("title", ""),
                brand=item.get("brand") or None,
                lprice=int(item.get("lprice", 0)),
                hprice=int(item.get("hprice", 0)),
                mall_name=item.get("mallName", ""),
                product_id=item.get("productId", ""),
                product_url=item.get("link", ""),
                category=item.get("category1") or None,
            )
            for item in data.get("items", [])
        ]

    async def get_top_keywords(
        self,
        category_name: str,
        start_date: date,
        end_date: date,
        top_n: int = 20,
    ) -> list[str]:
        """특정 기간 동안 카테고리 인기 키워드 Top N 반환."""
        category_id = BEAUTY_CATEGORIES.get(category_name)
        if not category_id:
            return []

        await self._wait_rate_limit()
        payload = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "timeUnit": "date",
            "category": [{"name": category_name, "param": [category_id]}],
            "keyword": [],
            "device": "",
            "ages": [],
            "gender": "",
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    INSIGHT_API,
                    headers={**self._headers, "Content-Type": "application/json"},
                    json=payload,
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            if not results:
                return []

            # 기간 내 평균 ratio 기준 정렬
            keyword_scores: dict[str, float] = {}
            for result in results:
                title = result.get("title", "")
                ratios = [d.get("ratio", 0) for d in result.get("data", [])]
                keyword_scores[title] = sum(ratios) / len(ratios) if ratios else 0.0

            sorted_kw = sorted(keyword_scores, key=lambda k: keyword_scores[k], reverse=True)
            return sorted_kw[:top_n]

        except Exception:
            return []

    async def get_bestsellers_during_event(
        self,
        event_name: str,
        start_date: date,
        end_date: date,
    ) -> list[str]:
        """행사 기간 동안 인기 상품 키워드 Top 20 (전 카테고리 합산)."""
        tasks = [
            self.get_top_keywords(cat, start_date, end_date, top_n=10)
            for cat in BEAUTY_CATEGORIES
        ]
        results = await asyncio.gather(*tasks)
        seen: set[str] = set()
        merged: list[str] = []
        for keywords in results:
            for kw in keywords:
                if kw not in seen:
                    seen.add(kw)
                    merged.append(kw)
                if len(merged) >= 20:
                    return merged
        return merged
