"""브랜드 공홈(Shopify products.json) 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from typing import Any

from app.scrapers.brands.shopify import (
    SKIIOfficialScraper,
    TatchaOfficialScraper,
    parse_products,
)

_BASE = "https://www.tatcha.com"


def _payload(*products: dict[str, Any]) -> dict[str, Any]:
    return {"products": list(products)}


def test_compare_at_price_becomes_original_price() -> None:
    """compare_at_price가 정가다 — 할인 여부를 추론하지 않고 값으로 안다."""
    events = parse_products(
        _payload({
            "title": "The Starter Ritual Set",
            "handle": "starter-ritual",
            "variants": [{"price": "75.00", "compare_at_price": "103.00"}],
        }),
        query="starter ritual",
        brand="Tatcha",
        base_url=_BASE,
    )
    assert len(events) == 1
    e = events[0]
    assert e.sale_price == 75.0
    assert e.original_price == 103.0
    assert e.discount_rate == 27.2
    assert e.source_url == f"{_BASE}/products/starter-ritual"


def test_no_discount_leaves_original_price_empty() -> None:
    """compare_at_price가 없거나 판매가 이하면 할인이 아니다."""
    events = parse_products(
        _payload({
            "title": "Dewy Serum",
            "handle": "dewy",
            "variants": [{"price": "88.00", "compare_at_price": None}],
        }),
        query="dewy",
        brand="Tatcha",
        base_url=_BASE,
    )
    assert events[0].original_price is None
    assert events[0].discount_rate is None


def test_compare_at_below_price_is_not_a_discount() -> None:
    events = parse_products(
        _payload({
            "title": "Cleanser",
            "handle": "cleanser",
            "variants": [{"price": "40.00", "compare_at_price": "30.00"}],
        }),
        query="cleanser",
        brand="Tatcha",
        base_url=_BASE,
    )
    assert events[0].original_price is None


def test_cheapest_variant_wins() -> None:
    """사이즈별로 가격이 갈린다 — 표시가는 최저가 기준."""
    events = parse_products(
        _payload({
            "title": "Essence",
            "handle": "essence",
            "variants": [
                {"price": "205.00", "compare_at_price": None},
                {"price": "99.00", "compare_at_price": "120.00"},
            ],
        }),
        query="essence",
        brand="SK-II",
        base_url=_BASE,
    )
    assert events[0].sale_price == 99.0
    assert events[0].original_price == 120.0


def test_query_filters_catalog() -> None:
    """products.json은 검색이 아니라 카탈로그 — 쿼리와 무관한 상품은 버린다."""
    events = parse_products(
        _payload(
            {"title": "Facial Treatment Essence", "handle": "fte",
             "variants": [{"price": "99.00"}]},
            {"title": "Lip Balm", "handle": "lip", "variants": [{"price": "20.00"}]},
        ),
        query="facial treatment essence",
        brand="SK-II",
        base_url=_BASE,
    )
    assert [e.product_name for e in events] == ["Facial Treatment Essence"]


def test_product_without_price_is_skipped() -> None:
    events = parse_products(
        _payload({"title": "Sample", "handle": "s", "variants": [{"price": None}]}),
        query="sample",
        brand="SK-II",
        base_url=_BASE,
    )
    assert events == []


def test_subclass_platform_attrs() -> None:
    assert SKIIOfficialScraper().PLATFORM_NAME == "SK-II 공홈"
    assert SKIIOfficialScraper().DOMAIN == "www.sk-ii.com"
    assert TatchaOfficialScraper().BRAND == "Tatcha"
