"""Quote generation — dynamic width, both-sided mandate.

DO:  widen proportional to recent volatility
     always generate both sides; two-sided required for reward when mid ∈ [0.10, 0.90]
DON'T: use fixed quote_width regardless of volatility
        place single-sided quotes when mid is between 0.10–0.90 (reward = 0)
"""
from __future__ import annotations
from dataclasses import dataclass

from config import QUOTE_WIDTH, VOL_WIDTH_K, ORDER_SIZE_USDC


@dataclass
class Quote:
    bid: float
    ask: float
    size_usdc: float
    both_sides: bool


def make_quote(
    best_bid: float,
    best_ask: float,
    recent_volatility: float = 0.0,
    *,
    size_usdc: float = ORDER_SIZE_USDC,
) -> Quote:
    mid = (best_bid + best_ask) / 2
    half = max(QUOTE_WIDTH, VOL_WIDTH_K * recent_volatility)
    bid = max(0.01, min(0.99, round(mid - half, 4)))
    ask = max(0.01, min(0.99, round(mid + half, 4)))
    return Quote(bid=bid, ask=ask, size_usdc=size_usdc, both_sides=True)


def compute_volatility(price_history: list[float]) -> float:
    """Std-dev of recent absolute price changes as volatility proxy."""
    if len(price_history) < 2:
        return 0.0
    changes = [abs(price_history[i] - price_history[i - 1]) for i in range(1, len(price_history))]
    mean = sum(changes) / len(changes)
    variance = sum((c - mean) ** 2 for c in changes) / len(changes)
    return variance ** 0.5
