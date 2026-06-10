"""Amazon US 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from app.scrapers.us.amazon import AmazonScraper, _parse_price, parse_search_html


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
    <div data-component-type="s-search-result">
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
