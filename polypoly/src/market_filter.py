"""Market filter — pure functions only (no network calls).

DO:  keep deterministic so replay produces the same candidate set
     score by fee_adjusted_edge and reward eligibility
DON'T: embed network calls (pass pre-fetched Market objects in)
        quote midpoints outside [0.10, 0.90] without forcing two-sided quotes
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from config import (
    MIN_VOLUME_24H, MIN_LIQUIDITY, MIN_SPREAD, MAX_SPREAD,
    MIN_DAYS_TO_EXPIRY, MID_PRICE_MIN, MID_PRICE_MAX,
)
from src.fees import fee_adjusted_edge
from src.gamma_client import Market


@dataclass
class FilteredMarket:
    market: Market
    fee_edge: float
    reward_eligible: bool
    score: float


def _days_to_expiry(end_date: str, now_ts: float) -> float:
    if not end_date:
        return 999.0
    try:
        dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        return max(0.0, (dt.timestamp() - now_ts) / 86_400)
    except ValueError:
        return 999.0


def filter_markets(markets: list[Market], now_ts: float) -> list[FilteredMarket]:
    """Apply §3.3 filters; return candidates ranked by fee-adjusted score."""
    results: list[FilteredMarket] = []
    for m in markets:
        if m.volume_24h < MIN_VOLUME_24H:
            continue
        if m.liquidity < MIN_LIQUIDITY:
            continue
        if not (MIN_SPREAD <= m.spread <= MAX_SPREAD):
            continue
        if _days_to_expiry(m.end_date, now_ts) < MIN_DAYS_TO_EXPIRY:
            continue
        if not (MID_PRICE_MIN <= m.mid <= MID_PRICE_MAX):
            continue
        edge = fee_adjusted_edge(m.best_bid, m.best_ask, m.category)
        if edge <= 0:
            continue
        score = edge + 0.01  # mid already confirmed in [0.10, 0.90] → reward eligible
        results.append(FilteredMarket(m, edge, reward_eligible=True, score=score))
    return sorted(results, key=lambda x: -x.score)
