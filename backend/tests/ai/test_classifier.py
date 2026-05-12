"""분류기 규칙 기반 로직 단위 테스트 (Claude API 호출 없음)."""
from datetime import date

from app.ai.classifier import classify_rule_based


def test_black_friday_classified_as_regular() -> None:
    result = classify_rule_based("블랙프라이데이", None, date(2024, 11, 22))
    assert result is not None
    assert result.event_type == "regular"
    assert result.confidence >= 0.9


def test_618_classified_as_regular() -> None:
    result = classify_rule_based("618 대세일", None, date(2024, 6, 18))
    assert result is not None
    assert result.event_type == "regular"


def test_stock_clearance_classified_as_surprise() -> None:
    result = classify_rule_based("특가", "재고소진", None)
    assert result is not None
    assert result.event_type == "surprise"


def test_new_product_launch_classified_as_surprise() -> None:
    result = classify_rule_based("출시 기념", "신제품 출시로 구버전 할인", None)
    assert result is not None
    assert result.event_type == "surprise"


def test_unknown_event_returns_none() -> None:
    result = classify_rule_based("여름 특가", "여름 시즌", date(2024, 7, 1))
    assert result is None  # Claude에게 위임
