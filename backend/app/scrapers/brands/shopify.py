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
from app.core.size import parse_size_ml
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

        # 가장 싼 판매 가능 variant 기준 (사이즈별로 가격이 갈린다).
        # variant.title이 용량이다("2.5 oz") — 상품명엔 없으므로 여기서 안 뽑으면
        # 용량 정보가 파이프라인에 아예 안 실린다.
        priced = [
            (
                _to_float(v.get("price")),
                _to_float(v.get("compare_at_price")),
                parse_size_ml(str(v.get("title") or "")),
            )
            for v in variants
        ]
        priced = [(p, c, s) for p, c, s in priced if p]
        if not priced:
            continue
        sale_price, compare_at, size_ml = min(priced, key=lambda tri: tri[0] or 0.0)
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
                size_ml=size_ml or parse_size_ml(title),
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


# (플랫폼명, 도메인, 브랜드). 전부 2026-08-05에 products.json 응답을 실측 확인했다.
# 추가 전에는 반드시 `curl https://<도메인>/products.json?limit=5`로 확인할 것 —
# Shopify여도 엔드포인트를 닫아둔 곳이 있다(Drunk Elephant 410, Fresh·YTTP 403).
BRANDS: list[tuple[str, str, str]] = [
    ("SK-II 공홈", "www.sk-ii.com", "SK-II"),
    ("Tatcha 공홈", "www.tatcha.com", "Tatcha"),
    ("La Prairie 공홈", "www.laprairie.com", "La Prairie"),
    ("Glossier 공홈", "www.glossier.com", "Glossier"),
    # K-beauty (미국 법인몰)
    ("Laneige 공홈", "us.laneige.com", "Laneige"),
    ("Sulwhasoo 공홈", "us.sulwhasoo.com", "Sulwhasoo"),
    ("Amorepacific 공홈", "us.amorepacific.com", "Amorepacific"),
    ("Innisfree 공홈", "us.innisfree.com", "innisfree"),
    ("Beauty of Joseon 공홈", "beautyofjoseon.com", "Beauty of Joseon"),
    ("COSRX 공홈", "www.cosrx.com", "COSRX"),
    # 프레스티지 스킨케어
    ("Sunday Riley 공홈", "sundayriley.com", "Sunday Riley"),
    ("Tata Harper 공홈", "www.tataharperskincare.com", "Tata Harper"),
    ("111Skin 공홈", "www.111skin.com", "111SKIN"),
    ("Herbivore 공홈", "www.herbivorebotanicals.com", "Herbivore"),
    ("Osea 공홈", "oseamalibu.com", "OSEA"),
    ("Summer Fridays 공홈", "summerfridays.com", "Summer Fridays"),
    ("Necessaire 공홈", "necessaire.com", "Nécessaire"),
    # 메이크업
    ("Westman Atelier 공홈", "westman-atelier.com", "Westman Atelier"),
    ("Victoria Beckham 공홈", "victoriabeckhambeauty.com", "Victoria Beckham Beauty"),
    ("ILIA 공홈", "iliabeauty.com", "ILIA"),
    ("Kosas 공홈", "kosas.com", "Kosas"),
    ("Merit 공홈", "meritbeauty.com", "MERIT"),
    ("Rare Beauty 공홈", "www.rarebeauty.com", "Rare Beauty"),
    ("Saie 공홈", "saiehello.com", "Saie"),
    ("Natasha Denona 공홈", "natashadenona.com", "Natasha Denona"),
    ("Pat McGrath 공홈", "www.patmcgrath.com", "Pat McGrath Labs"),
]


def _brand_class(platform_name: str, domain: str, brand: str) -> type[ShopifyBrandScraper]:
    """브랜드별 서브클래스를 레지스트리에서 생성. 26개를 손으로 쓰지 않는다."""
    class_name = "".join(ch for ch in brand.title() if ch.isalnum()) + "OfficialScraper"
    return type(
        class_name,
        (ShopifyBrandScraper,),
        {"PLATFORM_NAME": platform_name, "DOMAIN": domain, "BRAND": brand},
    )


BRAND_SCRAPERS: dict[str, type[ShopifyBrandScraper]] = {
    platform_name: _brand_class(platform_name, domain, brand)
    for platform_name, domain, brand in BRANDS
}
