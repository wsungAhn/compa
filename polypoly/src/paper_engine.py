"""Paper fill engine — the heart of the experiment.

Fill model must be conservative or the entire paper→live comparison is invalid.

DO:
  fill_qty = max(0, traded_volume_through_price - queue_ahead)
  mark at mid_after_trade (not fill price) to surface adverse selection
  store both conservative and aggressive; use ONLY conservative * FILL_HAIRCUT for decisions
  compute all PnL net of taker fee (hypothetical liquidation cost)

DON'T:
  assume full fill whenever price crosses our level (queue-blind → over-counts fills)
  mark at fill price (hides adverse selection, inflates paper PnL)
  use gross spread as profit
  use aggressive model for the live transition decision
"""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import NamedTuple

from config import FILL_HAIRCUT
from src.clob_client import TradeTick
from src.fees import taker_fee


@dataclass
class PaperOrder:
    market_id: str
    token_id: str
    side: str        # "BID" | "ASK"
    price: float
    size_usdc: float
    placed_at: float
    category: str = "other"


@dataclass
class PaperFill:
    order: PaperOrder
    fill_qty_conservative: float  # max(0, traded_through - queue_ahead)
    fill_qty_aggressive: float    # raw tick size (queue-blind, for logging only)
    mark_price: float             # mid AFTER the trade tick — not fill price
    timestamp: float
    net_pnl: float                # marked-to-mid minus hypothetical liquidation fee

    @property
    def fill_qty(self) -> float:
        """Decision-grade quantity: conservative * FILL_HAIRCUT."""
        return self.fill_qty_conservative * FILL_HAIRCUT


class FillResult(NamedTuple):
    filled: bool
    fill: PaperFill | None


def estimate_fill(
    order: PaperOrder,
    tick: TradeTick,
    *,
    mid_after: float,
    queue_ahead: float = 0.0,  # resting size ahead of us at the same price level
) -> FillResult:
    crosses = (
        (order.side == "BID" and tick.price <= order.price) or
        (order.side == "ASK" and tick.price >= order.price)
    )
    if not crosses:
        return FillResult(False, None)

    aggressive = tick.size
    conservative = max(0.0, tick.size - queue_ahead)
    if conservative <= 0:
        return FillResult(False, None)

    qty = conservative * FILL_HAIRCUT
    unrealized = qty * (mid_after - order.price) if order.side == "BID" else qty * (order.price - mid_after)
    net_pnl = unrealized - qty * taker_fee(order.category)

    return FillResult(True, PaperFill(
        order=order,
        fill_qty_conservative=conservative,
        fill_qty_aggressive=aggressive,
        mark_price=mid_after,
        timestamp=tick.timestamp,
        net_pnl=net_pnl,
    ))
