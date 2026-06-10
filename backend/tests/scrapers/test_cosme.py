"""@cosme JP 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
from app.scrapers.jp.cosme import CosmeScraper, _parse_jpy, parse_search_html


def test_parse_jpy_with_yen_symbol() -> None:
    assert _parse_jpy("¥3000") == 3000.0


def test_parse_jpy_with_yen_character() -> None:
    assert _parse_jpy("3000円") == 3000.0


def test_parse_jpy_with_comma() -> None:
    assert _parse_jpy("¥10,500") == 10500.0


def test_parse_jpy_with_comma_and_yen_char() -> None:
    assert _parse_jpy("5,500円") == 5500.0


def test_parse_jpy_invalid() -> None:
    assert _parse_jpy("abc") is None


def test_parse_jpy_empty() -> None:
    assert _parse_jpy("") is None


def test_scraper_platform_attrs() -> None:
    scraper = CosmeScraper()
    assert scraper.PLATFORM_NAME == "@cosme"
    assert scraper.COUNTRY == "JP"
    assert scraper.RATE_LIMIT_SEC == 1.5


def test_parse_search_html_empty() -> None:
    html = ""
    events = parse_search_html(html, "http://example.com")
    assert events == []


def test_parse_search_html_with_price() -> None:
    html = """
    <li class="item">
        <a class="product-name">テスト BBクリーム</a>
        <span class="price">¥2,500</span>
    </li>
    """
    url = "http://cosme.com/products/list.php?keyword=bbcream"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "テスト BBクリーム"
    assert event.sale_price == 2500.0
    assert event.original_price is None
    assert event.discount_rate is None
    assert event.currency == "JPY"
    assert event.event_name == "@cosme 現在価格"
    assert event.confidence == 0.75
    assert event.source_url == url


def test_parse_search_html_with_yen_char() -> None:
    """Test price parsing with 円 character."""
    html = """
    <li class="item">
        <a class="product-name">テスト 美容液</a>
        <span class="price">4,980円</span>
    </li>
    """
    url = "http://cosme.com/products/list.php?keyword=serum"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "テスト 美容液"
    assert event.sale_price == 4980.0


def test_parse_search_html_missing_price() -> None:
    """Product without price should be skipped."""
    html = """
    <li class="item">
        <a class="product-name">テスト 製品</a>
    </li>
    """
    url = "http://cosme.com/products/list.php?keyword=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_missing_name() -> None:
    """Product without name should be skipped."""
    html = """
    <li class="item">
        <span class="price">¥3000</span>
    </li>
    """
    url = "http://cosme.com/products/list.php?keyword=test"
    events = parse_search_html(html, url)

    assert events == []


def test_parse_search_html_fallback_selector() -> None:
    """Test fallback selectors when primary selectors missing."""
    html = """
    <div class="product-item">
        <a>テスト 化粧水</a>
        <div class="price">¥6,500</div>
    </div>
    """
    url = "http://cosme.com/products/list.php?keyword=lotion"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "テスト 化粧水"
    assert event.sale_price == 6500.0


def test_parse_search_html_max_five_items() -> None:
    """Should return at most 5 items."""
    html = ""
    for i in range(10):
        html += f"""
        <li class="item">
            <a class="product-name">製品 {i}</a>
            <span class="price">¥{1000 + i * 100}</span>
        </li>
        """
    url = "http://cosme.com/products/list.php?keyword=test"
    events = parse_search_html(html, url)

    assert len(events) == 5


def test_parse_search_html_price_in_text() -> None:
    """Test price extraction from general text content."""
    html = """
    <li class="item">
        <a>テスト パック</a>
        テスト パック 通常価格 ¥3,980
    </li>
    """
    url = "http://cosme.com/products/list.php?keyword=pack"
    events = parse_search_html(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "テスト パック"
    assert event.sale_price == 3980.0


def test_parse_search_html_invalid_price_format() -> None:
    """Product with non-parseable price format should be skipped."""
    html = """
    <li class="item">
        <a class="product-name">テスト マスク</a>
        <span class="price">問い合わせ</span>
    </li>
    """
    url = "http://cosme.com/products/list.php?keyword=mask"
    events = parse_search_html(html, url)

    assert events == []
