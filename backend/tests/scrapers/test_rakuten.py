"""楽天 スクレーパー 単体テスト (実際のHTTP呼び出しなし)."""
from typing import Any

from app.scrapers.jp.rakuten import RakutenScraper, parse_response


def test_scraper_platform_attrs() -> None:
    scraper = RakutenScraper()
    assert scraper.PLATFORM_NAME == "Rakuten"
    assert scraper.COUNTRY == "JP"
    assert scraper.RATE_LIMIT_SEC == 0.5


def test_parse_response_empty_dict() -> None:
    data: dict[str, Any] = {}
    events = parse_response(data, "test")
    assert events == []


def test_parse_response_empty_items() -> None:
    data: dict[str, Any] = {"Items": []}
    events = parse_response(data, "test")
    assert events == []


def test_parse_response_single_item() -> None:
    data: dict[str, Any] = {
        "Items": [
            {
                "Item": {
                    "itemName": "テストセラム",
                    "itemPrice": 1980,
                    "itemUrl": "https://item.rakuten.co.jp/shop/12345",
                    "itemCaption": "美容液",
                }
            }
        ]
    }
    query = "セラム"
    events = parse_response(data, query)

    assert len(events) == 1
    event = events[0]
    assert event.product_name == "テストセラム"
    assert event.sale_price == 1980.0
    assert event.currency == "JPY"
    assert event.event_name == "Rakuten 현재가"
    assert event.source_url == "https://item.rakuten.co.jp/shop/12345"
    assert event.confidence == 0.95
    assert event.raw_text == "美容液"


def test_parse_response_missing_price() -> None:
    """Item without price should be skipped."""
    data: dict[str, Any] = {
        "Items": [
            {
                "Item": {
                    "itemName": "テストセラム",
                    "itemUrl": "https://item.rakuten.co.jp/shop/12345",
                    "itemCaption": "美容液",
                }
            }
        ]
    }
    events = parse_response(data, "test")
    assert events == []


def test_parse_response_zero_price() -> None:
    """Item with zero price should be skipped."""
    data: dict[str, Any] = {
        "Items": [
            {
                "Item": {
                    "itemName": "テストセラム",
                    "itemPrice": 0,
                    "itemUrl": "https://item.rakuten.co.jp/shop/12345",
                    "itemCaption": "美容液",
                }
            }
        ]
    }
    events = parse_response(data, "test")
    assert events == []


def test_parse_response_multiple_items() -> None:
    data: dict[str, Any] = {
        "Items": [
            {
                "Item": {
                    "itemName": "テストセラム1",
                    "itemPrice": 1980,
                    "itemUrl": "https://item.rakuten.co.jp/shop/1",
                    "itemCaption": "美容液",
                }
            },
            {
                "Item": {
                    "itemName": "テストセラム2",
                    "itemPrice": 2500,
                    "itemUrl": "https://item.rakuten.co.jp/shop/2",
                    "itemCaption": "セラム",
                }
            },
        ]
    }
    query = "セラム"
    events = parse_response(data, query)

    assert len(events) == 2
    assert events[0].product_name == "テストセラム1"
    assert events[0].sale_price == 1980.0
    assert events[1].product_name == "テストセラム2"
    assert events[1].sale_price == 2500.0


def test_parse_response_missing_item_field() -> None:
    """Wrapper without Item field should be skipped gracefully."""
    data: dict[str, Any] = {
        "Items": [
            {},
            {
                "Item": {
                    "itemName": "テストセラム",
                    "itemPrice": 1980,
                    "itemUrl": "https://item.rakuten.co.jp/shop/12345",
                    "itemCaption": "美容液",
                }
            },
        ]
    }
    events = parse_response(data, "test")

    assert len(events) == 1
    assert events[0].product_name == "テストセラム"


def test_parse_response_default_product_name() -> None:
    """Item without itemName should use query as product name."""
    data: dict[str, Any] = {
        "Items": [
            {
                "Item": {
                    "itemPrice": 1980,
                    "itemUrl": "https://item.rakuten.co.jp/shop/12345",
                    "itemCaption": "美容液",
                }
            }
        ]
    }
    query = "default_query"
    events = parse_response(data, query)

    assert len(events) == 1
    assert events[0].product_name == "default_query"


def test_parse_response_missing_optional_fields() -> None:
    """Item with only required fields should still create event."""
    data: dict[str, Any] = {
        "Items": [
            {
                "Item": {
                    "itemPrice": 1980,
                }
            }
        ]
    }
    events = parse_response(data, "test")

    assert len(events) == 1
    event = events[0]
    assert event.sale_price == 1980.0
    assert event.source_url == ""
    assert event.raw_text == ""
