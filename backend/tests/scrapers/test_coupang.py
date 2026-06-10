"""쿠팡 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from app.scrapers.kr.coupang import CoupangScraper, _parse_price, parse_search_html


def test_parse_price_with_comma() -> None:
    assert _parse_price("12,000") == 12000.0


def test_parse_price_plain() -> None:
    assert _parse_price("9900") == 9900.0


def test_parse_price_empty() -> None:
    assert _parse_price("") is None


def test_parse_price_no_digits() -> None:
    assert _parse_price("가격 미정") is None


def test_scraper_platform_attrs() -> None:
    scraper = CoupangScraper()
    assert scraper.PLATFORM_NAME == "쿠팡"
    assert scraper.COUNTRY == "KR"
    assert scraper.RATE_LIMIT_SEC == 1.0


def test_parse_search_html_empty() -> None:
    html = ""
    events = parse_search_html(html, "http://example.com")
    assert events == []


def test_parse_search_html_with_discount() -> None:
    html = """
    <div class="search-product">
        <a class="product-name">테스트 상품 1</a>
        <strong class="price">8,900</strong>
        <del>12,000</del>
    </div>
    """
    url = "http://coupang.com/search?q=test"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "테스트 상품 1"
    assert event.sale_price == 8900.0
    assert event.original_price == 12000.0
    assert event.discount_rate == 25.8
    assert event.currency == "KRW"
    assert event.event_name == "쿠팡 할인"
    assert event.source_url == url
    assert event.confidence == 0.85


def test_parse_search_html_no_original_price() -> None:
    """Product without original price should be skipped."""
    html = """
    <div class="search-product">
        <a class="product-name">테스트 상품 2</a>
        <strong class="price">8,900</strong>
    </div>
    """
    url = "http://coupang.com/search?q=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_sale_not_less_than_original() -> None:
    """Product where sale >= original should be skipped."""
    html = """
    <div class="search-product">
        <a class="product-name">테스트 상품 3</a>
        <strong class="price">12,000</strong>
        <del>8,900</del>
    </div>
    """
    url = "http://coupang.com/search?q=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_with_base_price_selector() -> None:
    """Test alternate selector for original price (.base-price)."""
    html = """
    <li class="search-item">
        <a class="product-name">테스트 상품 4</a>
        <strong class="price">10,500</strong>
        <span class="base-price">15,000</span>
    </li>
    """
    url = "http://coupang.com/search?q=test"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.sale_price == 10500.0
    assert event.original_price == 15000.0
    assert event.discount_rate == 30.0
