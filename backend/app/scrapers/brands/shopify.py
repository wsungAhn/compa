# 브랜드 공홈(Shopify) 스크래퍼.
#
# 럭셔리 화장품 브랜드 상당수가 Shopify를 쓰고 표준 /products.json을 열어둔다.
# HTML 스크래핑과 달리 봇 차단이 없고, variants[].compare_at_price가 정가라서
# 할인 여부를 추론이 아니라 값으로 알 수 있다 (2026-08-05 실측: SK-II·Tatcha·
# La Prairie·Glossier 확인, Drunk Elephant는 410으로 비활성).
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from app.core.proxy import httpx_proxy
from app.scrapers.base import BaseScraper, ScrapedEvent

logger = logging.getLogger(__name__)

_PRODUCTS_PATH = "/products.json"
_LIMIT = 250


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _query_tokens(query: str) -> list[str]:
    """검색어를 토큰으로. 브랜드명은 공홈에선 모든 상품에 붙으므로 제외하지 않는다."""
    return [t for t in query.lower().replace("-", " ").split() if len(t) > 1]


def parse_products(
    payload: dict[str, Any], query: str, brand: str, base_url: str
) -> list[ScrapedEvent]:
    """Shopify products.json → ScrapedEvent.

    compare_at_price가 price보다 크면 그 차이가 곧 진행 중인 할인이다.
    """
    tokens = _query_tokens(query)
    events: list[ScrapedEvent] = []

    for product in payload.get("products") or []:
        title = str(product.get("title") or "").strip()
        if not title:
            continue

        haystack = f"{title} {product.get('product_type') or ''}".lower()
        if tokens and not any(t in haystack for t in tokens):
            continue

        variants = product.get("variants") or []
        if not variants:
            continue

        # 가장 싼 판매 가능 variant 기준 (사이즈별로 가격이 갈린다)
        priced = [
            (_to_float(v.get("price")), _to_float(v.get("compare_at_price")))
            for v in variants
        ]
        priced = [(p, c) for p, c in priced if p]
        if not priced:
            continue
        sale_price, compare_at = min(priced, key=lambda pair: pair[0] or 0.0)
        if not sale_price:
            continue

        original_price = compare_at if compare_at and compare_at > sale_price else None
        discount_rate = (
            round((original_price - sale_price) / original_price * 100, 1)
            if original_price
            else None
        )

        handle = product.get("handle")
        events.append(
            ScrapedEvent(
                product_name=title,
                brand=brand,
                original_price=original_price,
                sale_price=sale_price,
                discount_rate=discount_rate,
                currency="USD",
                start_date=date.today(),
                event_name=f"{brand} 공홈 {'할인' if original_price else '현재가'}",
                source_url=f"{base_url}/products/{handle}" if handle else base_url,
                confidence=0.95,
            )
        )

    return events


class ShopifyBrandScraper(BaseScraper):
    """서브클래스는 DOMAIN·PLATFORM_NAME·BRAND만 정의하면 된다."""

    DOMAIN: str = ""
    BRAND: str = ""
    COUNTRY = "US"
    RATE_LIMIT_SEC = 1.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        base_url = f"https://{self.DOMAIN}"
        url = f"{base_url}{_PRODUCTS_PATH}?limit={_LIMIT}"
        try:
            await self._wait_rate_limit()
            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, proxy=httpx_proxy()
            ) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                payload: dict[str, Any] = resp.json()
        except Exception as exc:
            logger.warning("%s products.json failed: %s", self.PLATFORM_NAME, exc)
            return [
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=f"{url}: {exc}",
                )
            ]

        events = parse_products(payload, query, self.BRAND, base_url)
        if not events and not payload.get("products"):
            # 빈 응답은 "할인 없음"이 아니라 엔드포인트가 닫혔다는 뜻이다.
            return [
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=f"{url}: products.json returned no products",
                )
            ]
        return events


class SKIIOfficialScraper(ShopifyBrandScraper):
    PLATFORM_NAME = "SK-II 공홈"
    DOMAIN = "www.sk-ii.com"
    BRAND = "SK-II"


class TatchaOfficialScraper(ShopifyBrandScraper):
    PLATFORM_NAME = "Tatcha 공홈"
    DOMAIN = "www.tatcha.com"
    BRAND = "Tatcha"


class LaPrairieOfficialScraper(ShopifyBrandScraper):
    PLATFORM_NAME = "La Prairie 공홈"
    DOMAIN = "www.laprairie.com"
    BRAND = "La Prairie"


class GlossierOfficialScraper(ShopifyBrandScraper):
    PLATFORM_NAME = "Glossier 공홈"
    DOMAIN = "www.glossier.com"
    BRAND = "Glossier"
