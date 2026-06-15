"""Tmall 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from app.scrapers.cn.tmall import TmallScraper, _parse_cny, parse_search_html


def test_parse_cny_with_yuan_symbol() -> None:
    assert _parse_cny("¥99.99") == 99.99


def test_parse_cny_with_comma() -> None:
    assert _parse_cny("¥1,299.99") == 1299.99


def test_parse_cny_plain() -> None:
    assert _parse_cny("199.50") == 199.50


def test_parse_cny_plain_integer() -> None:
    assert _parse_cny("299") == 299.0


def test_parse_cny_empty() -> None:
    assert _parse_cny("") is None


def test_parse_cny_no_digits() -> None:
    assert _parse_cny("价格未定") is None


def test_scraper_platform_attrs() -> None:
    scraper = TmallScraper()
    assert scraper.PLATFORM_NAME == "Tmall"
    assert scraper.COUNTRY == "CN"
    assert scraper.RATE_LIMIT_SEC == 2.0


def test_parse_search_html_empty() -> None:
    html = ""
    events = parse_search_html(html, "http://example.com")
    assert events == []


def test_parse_search_html_with_two_products() -> None:
    html = """
    <div class="product">
        <a class="productTitle" title="茵芙纯护肤品">茵芙纯</a>
        <div class="productPrice">
            <em title="¥59.99">¥59.99</em>
        </div>
    </div>
    <div class="product">
        <a class="productTitle" title="兰蔻粉水爽肤水">兰蔻粉水</a>
        <div class="productPrice">
            <em>¥189.00</em>
        </div>
    </div>
    """
    url = "http://tmall.com/search?q=skincare"
    events = parse_search_html(html, url)

    assert len(events) == 2
    assert events[0].product_name == "茵芙纯护肤品"
    assert events[0].sale_price == 59.99
    assert events[0].currency == "CNY"
    assert events[0].confidence == 0.7
    assert events[0].event_name == "Tmall 现价"

    assert events[1].product_name == "兰蔻粉水爽肤水"
    assert events[1].sale_price == 189.0
    assert events[1].event_name == "Tmall 现价"


def test_parse_search_html_missing_name() -> None:
    """Product without name should be skipped."""
    html = """
    <div class="product">
        <div class="productPrice">
            <em>¥99.99</em>
        </div>
    </div>
    """
    url = "http://tmall.com/search?q=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_missing_price() -> None:
    """Product without price should be skipped."""
    html = """
    <div class="product">
        <a class="productTitle">某产品</a>
    </div>
    """
    url = "http://tmall.com/search?q=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_fallback_selector() -> None:
    """Test fallback selectors when primary ones missing."""
    html = """
    <div class="product-item-container">
        <a title="护肤品A">护肤品A</a>
        <div class="price-info">
            <span class="price">¥249.50</span>
        </div>
    </div>
    """
    url = "http://tmall.com/search?q=skincare"
    events = parse_search_html(html, url)

    assert len(events) == 1
    assert events[0].sale_price == 249.50


def test_parse_search_html_max_five_items() -> None:
    """Should return at most 5 items."""
    html = ""
    for i in range(10):
        html += f"""
        <div class="product">
            <a class="productTitle" title="Product {i}">Product {i}</a>
            <div class="productPrice">
                <em>¥{100 + i}.00</em>
            </div>
        </div>
        """
    url = "http://tmall.com/search?q=test"
    events = parse_search_html(html, url)

    assert len(events) == 5


def test_parse_search_html_fallback_j_titems() -> None:
    """Test J_TItems selector which uses data-id attribute."""
    html = """
    <div class="J_TItems" data-id="123456">
        <a href="#" title="彩妆品B">彩妆品B</a>
        <div class="productPrice">
            <em>¥129.99</em>
        </div>
    </div>
    """
    url = "http://tmall.com/search?q=makeup"
    events = parse_search_html(html, url)

    assert len(events) == 1
    assert events[0].product_name == "彩妆品B"
    assert events[0].sale_price == 129.99
