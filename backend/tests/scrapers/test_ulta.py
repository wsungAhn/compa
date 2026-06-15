"""Ulta US 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from app.scrapers.us.ulta import UltaScraper, _parse_usd, parse_search_html


def test_parse_usd_with_cents() -> None:
    assert _parse_usd("$29.99") == 29.99


def test_parse_usd_with_comma() -> None:
    assert _parse_usd("$1,299.99") == 1299.99


def test_parse_usd_plain() -> None:
    assert _parse_usd("$99") == 99.0


def test_parse_usd_invalid() -> None:
    assert _parse_usd("abc") is None


def test_parse_usd_empty() -> None:
    assert _parse_usd("") is None


def test_scraper_platform_attrs() -> None:
    scraper = UltaScraper()
    assert scraper.PLATFORM_NAME == "Ulta"
    assert scraper.COUNTRY == "US"
    assert scraper.RATE_LIMIT_SEC == 2.0


def test_parse_search_html_empty() -> None:
    html = ""
    events = parse_search_html(html, "http://example.com")
    assert events == []


def test_parse_search_html_with_discount() -> None:
    html = """
    <div data-test="product-card">
        <a data-test="product-name">Test Mascara</a>
        <span data-test="product-price">$19.99</span>
        <s>$29.99</s>
    </div>
    """
    url = "http://ulta.com/shop/search?search=mascara"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "Test Mascara"
    assert event.sale_price == 19.99
    assert event.original_price == 29.99
    assert event.discount_rate == 33.3
    assert event.currency == "USD"
    assert event.event_name == "Ulta 할인"
    assert event.confidence == 0.8
    assert event.source_url == url


def test_parse_search_html_without_original_price() -> None:
    """Product without original price should use current price event."""
    html = """
    <div data-test="product-card">
        <a data-test="product-name">Test Foundation</a>
        <span data-test="product-price">$35.00</span>
    </div>
    """
    url = "http://ulta.com/shop/search?search=foundation"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "Test Foundation"
    assert event.sale_price == 35.00
    assert event.original_price is None
    assert event.discount_rate is None
    assert event.event_name == "Ulta 현재가"
    assert event.confidence == 0.8


def test_parse_search_html_missing_price() -> None:
    """Product without price should be skipped."""
    html = """
    <div data-test="product-card">
        <a data-test="product-name">Test Product</a>
    </div>
    """
    url = "http://ulta.com/shop/search?search=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_missing_name() -> None:
    """Product without name should be skipped."""
    html = """
    <div data-test="product-card">
        <span data-test="product-price">$25.00</span>
    </div>
    """
    url = "http://ulta.com/shop/search?search=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_fallback_selector() -> None:
    """Test fallback selectors when data-test attributes missing."""
    html = """
    <div class="ProductCard">
        <a class="ProductCard__name">Test Lipstick</a>
        <span class="ProductCard__price">$22.50</span>
        <span class="ProductCard__originalPrice">$30.00</span>
    </div>
    """
    url = "http://ulta.com/shop/search?search=lipstick"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "Test Lipstick"
    assert event.sale_price == 22.50
    assert event.original_price == 30.00
    assert event.discount_rate == 25.0
    assert event.event_name == "Ulta 할인"


def test_parse_search_html_max_five_items() -> None:
    """Should return at most 5 items."""
    html = ""
    for i in range(10):
        html += f"""
        <div data-test="product-card">
            <a data-test="product-name">Product {i}</a>
            <span data-test="product-price">${i + 10}.00</span>
        </div>
        """
    url = "http://ulta.com/shop/search?search=test"
    events = parse_search_html(html, url)

    assert len(events) == 5


def test_parse_search_html_strikethrough_price() -> None:
    """Test using del tag for original price."""
    html = """
    <div data-test="product-card">
        <a data-test="product-name">Test Eyeshadow</a>
        <span data-test="product-price">$14.99</span>
        <del>$20.00</del>
    </div>
    """
    url = "http://ulta.com/shop/search?search=eyeshadow"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.original_price == 20.00
    assert event.discount_rate == 25.0
