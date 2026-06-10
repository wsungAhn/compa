"""수집기 분류 로직 단위 테스트."""
from datetime import date

from app.scrapers.base import ScrapedEvent
from app.scrapers.collector import _classify_event_type


def test_classify_event_type_regular_by_known_event() -> None:
    """올영세일은 정기 행사로 분류."""
    s = ScrapedEvent(
        product_name="설화수 윤조에센스",
        event_name="올영세일",
        reason=None,
        start_date=None,
    )
    result = _classify_event_type(s)
    assert result == "regular"


def test_classify_event_type_surprise_by_keyword() -> None:
    """재고소진 키워드는 돌발 행사로 분류."""
    s = ScrapedEvent(
        product_name="립스틱",
        event_name="특가",
        reason="재고소진",
        start_date=None,
    )
    result = _classify_event_type(s)
    assert result == "surprise"


def test_classify_event_type_surprise_new_product() -> None:
    """신제품 출시는 돌발 행사로 분류."""
    s = ScrapedEvent(
        product_name="에센스",
        event_name="신제품 출시",
        reason="신제품 출시로 구버전 할인",
        start_date=None,
    )
    result = _classify_event_type(s)
    assert result == "surprise"


def test_classify_event_type_regular_black_friday() -> None:
    """블랙프라이데이는 정기 행사로 분류."""
    s = ScrapedEvent(
        product_name="크림",
        event_name="블랙프라이데이",
        reason=None,
        start_date=date(2024, 11, 29),
    )
    result = _classify_event_type(s)
    assert result == "regular"


def test_classify_event_type_unknown_returns_none() -> None:
    """미분류 행사는 None 반환 (나중에 Claude로 분류)."""
    s = ScrapedEvent(
        product_name="팩",
        event_name="여름 특가",
        reason="여름 시즌",
        start_date=date(2024, 7, 1),
    )
    result = _classify_event_type(s)
    assert result is None
