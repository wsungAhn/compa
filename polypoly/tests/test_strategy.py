import pytest
from src.strategy import make_quote, compute_volatility


def test_both_sides_always_generated() -> None:
    q = make_quote(0.48, 0.52)
    assert q.bid < q.ask
    assert q.both_sides


def test_widens_with_volatility() -> None:
    lo = make_quote(0.48, 0.52, recent_volatility=0.001)
    hi = make_quote(0.48, 0.52, recent_volatility=0.10)
    assert (hi.ask - hi.bid) >= (lo.ask - lo.bid)


def test_prices_clamped() -> None:
    q = make_quote(0.01, 0.03)
    assert 0.01 <= q.bid <= 0.99
    assert 0.01 <= q.ask <= 0.99


def test_volatility_zero_on_flat() -> None:
    assert compute_volatility([0.5, 0.5, 0.5]) == pytest.approx(0.0)


def test_volatility_nonzero() -> None:
    assert compute_volatility([0.4, 0.7, 0.5]) > 0
