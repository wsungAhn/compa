"""Risk — pre-trade checks, dynamic width, skew detection.

DO:
  check ALL limits BEFORE placing any paper order (pre-trade gate)
  widen quote dynamically when recent volatility rises
  detect fill skew (picked-off signal) and back off
  group correlated markets into clusters; enforce cluster-level limits

DON'T:
  use post-trade checks only (damage already recorded)
  keep fixed quote_width in volatile conditions
  treat all markets as independent (same event moves legs together)
"""
from __future__ import annotations
from dataclasses import dataclass

from config import (
    MAX_POSITION_PER_MARKET,
    MAX_TOTAL_EXPOSURE,
    MAX_CLUSTER_EXPOSURE,
    STOP_IF_5MIN_MOVE_GT,
)


@dataclass
class RiskCheck:
    allowed: bool
    reason: str = ""


def check_pre_trade(
    *,
    market_id: str,
    cluster_id: str,
    order_notional: float,
    current_position: float,
    total_exposure: float,
    cluster_exposure: float,
) -> RiskCheck:
    if current_position + order_notional > MAX_POSITION_PER_MARKET:
        return RiskCheck(False, f"position limit {MAX_POSITION_PER_MARKET}")
    if total_exposure + order_notional > MAX_TOTAL_EXPOSURE:
        return RiskCheck(False, f"total exposure limit {MAX_TOTAL_EXPOSURE}")
    if cluster_id and cluster_exposure + order_notional > MAX_CLUSTER_EXPOSURE:
        return RiskCheck(False, f"cluster limit {MAX_CLUSTER_EXPOSURE}")
    return RiskCheck(True)


def check_stop_quote(price_history_5min: list[float]) -> bool:
    """True → halt quoting; recent 5-min move exceeds threshold."""
    if len(price_history_5min) < 2:
        return False
    return abs(price_history_5min[-1] - price_history_5min[0]) > STOP_IF_5MIN_MOVE_GT


def dynamic_quote_width(base_width: float, recent_volatility: float, k: float = 1.0) -> float:
    return max(base_width, k * recent_volatility)


def is_skewed_fills(fill_sides: list[str], threshold: int = 3) -> bool:
    """True when the last `threshold` fills are all on the same side (picked-off signal)."""
    if len(fill_sides) < threshold:
        return False
    return len(set(fill_sides[-threshold:])) == 1
