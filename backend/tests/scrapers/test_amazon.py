"""Amazon US 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from typing import Any

from app.scrapers.us.amazon import (
    AmazonScraper,
    _parse_price,
    build_paapi_request,
    parse_paapi_response,
    parse_search_html,
    _sign_request_aws_v4,
)


def test_parse_price_with_whole_and_fraction() -> None:
    assert _parse_price("29", "99") == 29.99


def test_parse_price_with_comma() -> None:
    assert _parse_price("1,299", "99") == 1299.99


def test_parse_price_whole_only() -> None:
    assert _parse_price("99") == 99.0


def test_parse_price_invalid_whole() -> None:
    assert _parse_price("abc") is None


def test_parse_price_non_digit_whole() -> None:
    assert _parse_price("N/A", "99") is None


def test_scraper_platform_attrs() -> None:
    scraper = AmazonScraper()
    assert scraper.PLATFORM_NAME == "Amazon US"
    assert scraper.COUNTRY == "US"
    assert scraper.RATE_LIMIT_SEC == 2.0


def test_parse_search_html_empty() -> None:
    html = ""
    events = parse_search_html(html, "http://example.com")
    assert events == []


def test_parse_search_html_with_price_and_original() -> None:
    html = """
    <div data-component-type="s-search-result" data-asin="B0123456789">
        <h2><a href="/product-page"><span>Test Product 1</span></a></h2>
        <span class="a-price-whole">29.</span>
        <span class="a-price-fraction">99</span>
        <span class="a-text-price"><span class="a-offscreen">$40.00</span></span>
    </div>
    """
    url = "http://amazon.com/search?k=test"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "Test Product 1"
    assert event.sale_price == 29.99
    assert event.original_price == 40.0
    assert event.discount_rate == 25.0
    assert event.currency == "USD"
    assert event.event_name == "Amazon 현재가"
    assert event.confidence == 0.8
    assert event.external_id == "B0123456789"
    assert event.id_type == "asin"


def test_parse_search_html_missing_whole_price() -> None:
    """Product without whole price should be skipped."""
    html = """
    <div data-component-type="s-search-result">
        <h2><a href="/product-page"><span>Test Product 2</span></a></h2>
        <span class="a-price-fraction">99</span>
    </div>
    """
    url = "http://amazon.com/search?k=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_missing_sale_price_parsing() -> None:
    """Product where price parsing fails should be skipped."""
    html = """
    <div data-component-type="s-search-result">
        <h2><a href="/product-page"><span>Test Product 3</span></a></h2>
        <span class="a-price-whole">abc</span>
    </div>
    """
    url = "http://amazon.com/search?k=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_no_discount() -> None:
    """Product with no original price should still be included if sale price exists."""
    html = """
    <div data-component-type="s-search-result">
        <h2><a href="/product-page"><span>Test Product 4</span></a></h2>
        <span class="a-price-whole">19.</span>
        <span class="a-price-fraction">99</span>
    </div>
    """
    url = "http://amazon.com/search?k=test"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.sale_price == 19.99
    assert event.original_price is None
    assert event.discount_rate is None


def test_parse_search_html_source_url() -> None:
    """Verify source URL is constructed correctly."""
    html = """
    <div data-component-type="s-search-result">
        <h2><a href="/B0123456789-makeup"><span>Test Product</span></a></h2>
        <span class="a-price-whole">49.</span>
        <span class="a-price-fraction">99</span>
    </div>
    """
    url = "http://amazon.com/search?k=makeup"
    events = parse_search_html(html, url)

    assert len(events) == 1
    assert events[0].source_url == "https://www.amazon.com/B0123456789-makeup"


# PA-API Tests


def test_build_paapi_request() -> None:
    """Test PA-API request payload building."""
    query = "moisturizer"
    partner_tag = "test-partner-12"

    payload = build_paapi_request(query, partner_tag)

    assert payload["Keywords"] == "moisturizer"
    assert payload["SearchIndex"] == "Beauty"
    assert payload["ItemCount"] == 5
    assert payload["PartnerTag"] == "test-partner-12"
    assert payload["PartnerType"] == "Associates"
    assert payload["Marketplace"] == "www.amazon.com"
    assert "ItemInfo.Title" in payload["Resources"]
    assert "Offers.Listings.Price" in payload["Resources"]
    assert "Offers.Listings.SavingBasis" in payload["Resources"]


def test_sign_request_aws_v4_deterministic() -> None:
    """Test AWS Signature V4 is deterministic with fixed inputs."""
    payload = '{"test":"data"}'
    access_key = "AKIAIOSFODNN7EXAMPLE"
    secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    amz_date = "20260101T000000Z"
    date_stamp = "20260101"

    headers1 = _sign_request_aws_v4(payload, access_key, secret_key, amz_date, date_stamp)
    headers2 = _sign_request_aws_v4(payload, access_key, secret_key, amz_date, date_stamp)

    # Should be identical for same inputs
    assert headers1 == headers2

    # Check Authorization header structure
    auth_header = headers1["Authorization"]
    assert auth_header.startswith("AWS4-HMAC-SHA256 Credential=")
    assert f"{access_key}/{date_stamp}/us-east-1/ProductAdvertisingAPI/aws4_request" in auth_header
    assert "SignedHeaders=" in auth_header
    assert "Signature=" in auth_header

    # Verify all required headers present
    assert headers1["X-Amz-Date"] == amz_date
    assert headers1["X-Amz-Target"] == "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    assert headers1["Content-Type"] == "application/json; charset=utf-8"


def test_parse_paapi_response_with_items() -> None:
    """Test parsing PA-API response with valid items."""
    response: dict[str, Any] = {
        "SearchResult": {
            "Items": [
                {
                    "ASIN": "B0PAAPI1234",
                    "ItemInfo": {"Title": {"DisplayValue": "Test Moisturizer"}},
                    "Offers": {
                        "Listings": [
                            {
                                "Price": {"Amount": 29.99},
                                "SavingBasis": {"Amount": 39.99},
                            }
                        ]
                    },
                    "DetailPageURL": "https://amazon.com/Test-Moisturizer/dp/B0123",
                },
            ]
        }
    }

    events = parse_paapi_response(response, "https://example.com")

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "Test Moisturizer"
    assert event.sale_price == 29.99
    assert event.original_price == 39.99
    assert event.discount_rate == 25.0
    assert event.currency == "USD"
    assert event.event_name == "Amazon 현재가"
    assert event.confidence == 0.95
    assert event.source_url == "https://amazon.com/Test-Moisturizer/dp/B0123"
    assert event.external_id == "B0PAAPI1234"
    assert event.id_type == "asin"


def test_parse_paapi_response_without_asin_leaves_external_id_empty() -> None:
    response: dict[str, Any] = {
        "SearchResult": {
            "Items": [
                {
                    "ItemInfo": {"Title": {"DisplayValue": "Test Moisturizer"}},
                    "Offers": {"Listings": [{"Price": {"Amount": 29.99}}]},
                    "DetailPageURL": "https://amazon.com/Test-Moisturizer/dp/B0123",
                },
            ]
        }
    }

    events = parse_paapi_response(response, "https://example.com")

    assert len(events) == 1
    assert events[0].external_id is None
    assert events[0].id_type == "asin"


def test_parse_search_html_without_data_asin_leaves_external_id_empty() -> None:
    html = """
    <div data-component-type="s-search-result">
        <h2><a href="/product-page"><span>Test Product 1</span></a></h2>
        <span class="a-price-whole">29.</span>
        <span class="a-price-fraction">99</span>
    </div>
    """

    events = parse_search_html(html, "https://www.amazon.com/s?k=test")

    assert len(events) == 1
    assert events[0].external_id is None
    assert events[0].id_type == "asin"


def test_parse_paapi_response_missing_price() -> None:
    """Test parsing PA-API response where item lacks price."""
    response: dict[str, Any] = {
        "SearchResult": {
            "Items": [
                {
                    "ItemInfo": {"Title": {"DisplayValue": "Test Product"}},
                    "Offers": {"Listings": [{}]},  # No Price key
                }
            ]
        }
    }

    events = parse_paapi_response(response, "https://example.com")

    # Should skip item without price
    assert events == []


def test_parse_paapi_response_no_listings() -> None:
    """Test parsing PA-API response where item lacks listings."""
    response: dict[str, Any] = {
        "SearchResult": {
            "Items": [
                {
                    "ItemInfo": {"Title": {"DisplayValue": "Test Product"}},
                    "Offers": {"Listings": []},  # Empty listings
                }
            ]
        }
    }

    events = parse_paapi_response(response, "https://example.com")

    # Should skip item without listings
    assert events == []


def test_parse_paapi_response_with_discount() -> None:
    """Test parsing PA-API response with discount calculation."""
    response: dict[str, Any] = {
        "SearchResult": {
            "Items": [
                {
                    "ItemInfo": {"Title": {"DisplayValue": "Serum"}},
                    "Offers": {
                        "Listings": [
                            {
                                "Price": {"Amount": 19.99},
                                "SavingBasis": {"Amount": 49.99},
                            }
                        ]
                    },
                    "DetailPageURL": "https://amazon.com/serum/dp/B999",
                }
            ]
        }
    }

    events = parse_paapi_response(response, "https://example.com")

    assert len(events) == 1
    event = events[0]
    assert event.discount_rate == 60.0  # (1 - 19.99/49.99) * 100


def test_parse_paapi_response_no_original_price() -> None:
    """Test parsing PA-API response without original price (no discount)."""
    response: dict[str, Any] = {
        "SearchResult": {
            "Items": [
                {
                    "ItemInfo": {"Title": {"DisplayValue": "Product"}},
                    "Offers": {
                        "Listings": [
                            {
                                "Price": {"Amount": 24.99},
                                # No SavingBasis
                            }
                        ]
                    },
                    "DetailPageURL": "https://amazon.com/product/dp/B111",
                }
            ]
        }
    }

    events = parse_paapi_response(response, "https://example.com")

    assert len(events) == 1
    event = events[0]
    assert event.sale_price == 24.99
    assert event.original_price is None
    assert event.discount_rate is None


def test_parse_paapi_response_empty() -> None:
    """Test parsing empty PA-API response."""
    response: dict[str, Any] = {"SearchResult": {"Items": []}}

    events = parse_paapi_response(response, "https://example.com")

    assert events == []


def test_parse_paapi_response_invalid_structure() -> None:
    """Test parsing malformed PA-API response."""
    response: dict[str, Any] = {}  # Missing SearchResult

    events = parse_paapi_response(response, "https://example.com")

    assert events == []


_CURRENT_MARKUP = """
<div data-component-type="s-search-result">
  <h2><span>SK-II Facial Treatment Essence 230ml</span></h2>
  <span class="a-price-whole">190.</span><span class="a-price-fraction">00</span>
  <a class="a-link-normal" href="/dp/B00TEST"></a>
</div>
"""

_LEGACY_MARKUP = """
<div data-component-type="s-search-result">
  <h2><a><span>Legacy Titled Product</span></a></h2>
  <span class="a-price-whole">25.</span><span class="a-price-fraction">50</span>
</div>
"""

_NAMELESS_MARKUP = """
<div data-component-type="s-search-result">
  <h2></h2>
  <span class="a-price-whole">42.</span><span class="a-price-fraction">00</span>
</div>
"""


def test_parse_search_html_current_markup() -> None:
    """Amazon moved the title out of the anchor; "h2 a span" alone stopped matching."""
    events = parse_search_html(_CURRENT_MARKUP, "https://www.amazon.com/s?k=skii")
    assert len(events) == 1
    assert events[0].product_name == "SK-II Facial Treatment Essence 230ml"
    assert events[0].sale_price == 190.0


def test_parse_search_html_legacy_markup_still_parses() -> None:
    events = parse_search_html(_LEGACY_MARKUP, "https://www.amazon.com/s?k=x")
    assert len(events) == 1
    assert events[0].product_name == "Legacy Titled Product"


def test_parse_search_html_skips_nameless_result() -> None:
    """A priced-but-nameless row means the selector broke — it must not become a product."""
    assert parse_search_html(_NAMELESS_MARKUP, "https://www.amazon.com/s?k=x") == []


_2026_MARKUP = """
<div data-component-type="s-search-result">
  <div data-cy="title-recipe">
    <h2 class="a-size-mini s-line-clamp-1"><span class="a-size-base-plus">SK-II</span></h2>
    <a class="a-link-normal" href="/dp/B00TEST">
      <h2 class="a-size-base-plus"><span>Facial Treatment Essence 230ml</span></h2>
    </a>
  </div>
  <span class="a-price-whole">190.</span><span class="a-price-fraction">00</span>
</div>
"""


def test_parse_search_html_2026_title_recipe_markup() -> None:
    """The brand and the product title live in two separate h2s; plain "h2" gives only the brand."""
    events = parse_search_html(_2026_MARKUP, "https://www.amazon.com/s?k=skii")
    assert len(events) == 1
    assert events[0].product_name == "SK-II Facial Treatment Essence 230ml"
    assert events[0].brand == "SK-II"


_BAD_ORIGINAL_MARKUP = """
<div data-component-type="s-search-result">
  <div data-cy="title-recipe">
    <h2 class="a-size-mini s-line-clamp-1"><span>SK-II</span></h2>
    <a href="/dp/B0"><h2 class="a-size-base-plus"><span>Essence</span></h2></a>
  </div>
  <span class="a-price-whole">190.</span><span class="a-price-fraction">00</span>
  <span class="a-text-price"><span class="a-offscreen">$35.00</span></span>
</div>
"""


def test_original_price_below_sale_price_is_dropped() -> None:
    """a-text-price가 단위가격을 담을 때가 있다 — 그대로 두면 음수 할인이 된다."""
    events = parse_search_html(_BAD_ORIGINAL_MARKUP, "https://www.amazon.com/s?k=x")
    assert len(events) == 1
    assert events[0].sale_price == 190.0
    assert events[0].original_price is None
    assert events[0].discount_rate is None
