import pytest
from src.risk import check_pre_trade, check_stop_quote, is_skewed_fills, dynamic_quote_width


def test_allowed() -> None:
    r = check_pre_trade(
        market_id="m1", cluster_id="", order_notional=10.0,
        current_position=0.0, total_exposure=0.0, cluster_exposure=0.0,
    )
    assert r.allowed


def test_blocked_position_limit() -> None:
    r = check_pre_trade(
        market_id="m1", cluster_id="", order_notional=50.0,
        current_position=10.0, total_exposure=10.0, cluster_exposure=0.0,
    )
    assert not r.allowed


def test_blocked_total_exposure() -> None:
    r = check_pre_trade(
        market_id="m1", cluster_id="", order_notional=10.0,
        current_position=0.0, total_exposure=395.0, cluster_exposure=0.0,
    )
    assert not r.allowed


def test_stop_quote_false() -> None:
    assert not check_stop_quote([0.50, 0.51, 0.52, 0.53, 0.54])


def test_stop_quote_true() -> None:
    assert check_stop_quote([0.50, 0.56])  # 0.06 > 0.05


def test_skewed_detected() -> None:
    assert is_skewed_fills(["BID", "BID", "BID"], threshold=3)


def test_skewed_not_detected_mixed() -> None:
    assert not is_skewed_fills(["BID", "ASK", "BID"], threshold=3)


def test_dynamic_width_base() -> None:
    assert dynamic_quote_width(0.01, 0.001) == pytest.approx(0.01)


def test_dynamic_width_expands() -> None:
    assert dynamic_quote_width(0.01, 0.05) == pytest.approx(0.05)
