import time
import pytest
from src.paper_engine import PaperOrder, estimate_fill
from src.clob_client import TradeTick
from config import FILL_HAIRCUT


def _bid(price: float = 0.49, category: str = "sports") -> PaperOrder:
    return PaperOrder(
        market_id="m1", token_id="t1", side="BID",
        price=price, size_usdc=10.0, placed_at=time.time(), category=category,
    )


def _tick(price: float, size: float = 100.0) -> TradeTick:
    return TradeTick(token_id="t1", timestamp=time.time(), price=price, size=size, side="SELL")


def test_no_fill_above_bid() -> None:
    assert not estimate_fill(_bid(0.49), _tick(0.50), mid_after=0.50).filled


def test_fill_below_bid() -> None:
    r = estimate_fill(_bid(0.49), _tick(0.48), mid_after=0.47)
    assert r.filled and r.fill is not None


def test_queue_reduces_fill() -> None:
    r = estimate_fill(_bid(0.49), _tick(0.48, size=50.0), mid_after=0.47, queue_ahead=40.0)
    assert r.filled
    assert r.fill is not None
    assert r.fill.fill_qty_conservative == pytest.approx(10.0)
    assert r.fill.fill_qty == pytest.approx(10.0 * FILL_HAIRCUT)


def test_queue_wipes_fill() -> None:
    assert not estimate_fill(_bid(0.49), _tick(0.48, size=50.0), mid_after=0.47, queue_ahead=50.0).filled


def test_adverse_selection_negative_pnl() -> None:
    # Sharp drop after fill → net_pnl should be negative
    r = estimate_fill(_bid(0.49), _tick(0.48, size=100.0), mid_after=0.35, queue_ahead=0)
    assert r.fill is not None
    assert r.fill.net_pnl < 0
