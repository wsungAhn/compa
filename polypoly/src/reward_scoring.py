"""Reward scoring — candidate ranking with competitive denominator.

DO:
  estimate total_market_score from observed resting depth in reward band (band_depth.parquet)
  use this for ranking only — Polymarket formula is approximate
  require both sides when mid ∈ [0.10, 0.90] for any non-zero score

DON'T:
  compute estimated_daily_reward without a denominator (meaningless number)
  treat the estimate as a precise forecast (competition and time-weighting vary)
"""
from __future__ import annotations
from dataclasses import dataclass

from config import MID_PRICE_MIN, MID_PRICE_MAX


@dataclass
class RewardCandidate:
    market_id: str
    category: str
    my_score: float
    total_score_estimate: float  # approximated from observed band_depth
    reward_pool: float           # USDC/day from market metadata (0 if unknown)

    @property
    def estimated_daily_reward(self) -> float:
        if self.total_score_estimate <= 0:
            return 0.0
        return self.reward_pool * (self.my_score / self.total_score_estimate)


def score_quote(
    *,
    bid: float,
    ask: float,
    size_usdc: float,
    mid: float,
    max_spread_band: float,
    min_size_band: float,
    seconds_resting: float,
) -> float:
    """Estimate per-period score contribution.

    Simplified model: score = size * time * proximity_bonus.
    Both sides mandatory when mid ∈ [0.10, 0.90]; outside that range returns 0.
    """
    if not (MID_PRICE_MIN <= mid <= MID_PRICE_MAX):
        return 0.0
    spread = ask - bid
    if spread > max_spread_band or size_usdc < min_size_band:
        return 0.0
    proximity = 1.0 - (spread / max_spread_band)
    return size_usdc * seconds_resting * (1 + proximity)
