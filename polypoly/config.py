"""Single source of truth for all tunable parameters.

DO:  read fees and reward params from here; snapshot at collection time
DON'T: hard-code fee values in other modules
"""
from __future__ import annotations
import os
from typing import Final

# === Capital & Position ===
INITIAL_CAPITAL: Final[float] = 1_000.0
MAX_MARKETS: Final[int] = 10
ORDER_SIZE_USDC: Final[float] = 10.0
MAX_POSITION_PER_MARKET: Final[float] = 50.0
MAX_TOTAL_EXPOSURE: Final[float] = 400.0
MAX_CLUSTER_EXPOSURE: Final[float] = 75.0

# === Market Filter ===
MIN_VOLUME_24H: Final[float] = 10_000.0
MIN_LIQUIDITY: Final[float] = 5_000.0
MIN_SPREAD: Final[float] = 0.02
MAX_SPREAD: Final[float] = 0.08
MIN_DAYS_TO_EXPIRY: Final[int] = 2
MID_PRICE_MIN: Final[float] = 0.10
MID_PRICE_MAX: Final[float] = 0.90

# === Strategy ===
QUOTE_WIDTH: Final[float] = 0.01       # dynamic lower bound
VOL_WIDTH_K: Final[float] = 1.0        # half = max(QUOTE_WIDTH, K * recent_vol)
REFRESH_SECONDS: Final[int] = 10
STOP_IF_5MIN_MOVE_GT: Final[float] = 0.05

# === Paper Fill Model ===
FILL_HAIRCUT: Final[float] = 0.6       # 60% of queue-adjusted fill counts

# === 2026 Fee Schedule — verify against Polymarket docs; snapshot at collection time ===
TAKER_FEES: Final[dict[str, float]] = {
    "crypto":      0.07,
    "sports":      0.03,
    "finance":     0.04,
    "politics":    0.04,
    "tech":        0.04,
    "economy":     0.05,
    "culture":     0.05,
    "weather":     0.05,
    "other":       0.05,
    "geopolitics": 0.00,
    "world":       0.00,
}
MAKER_REBATE: Final[float] = 0.0125

# === API ===
GAMMA_API_BASE: Final[str] = os.getenv("GAMMA_API_BASE", "https://gamma-api.polymarket.com")
CLOB_API_BASE:  Final[str] = os.getenv("CLOB_API_BASE",  "https://clob.polymarket.com")
CLOB_WS_BASE:   Final[str] = os.getenv("CLOB_WS_BASE",   "wss://ws-subscriptions-clob.polymarket.com/ws")

# Phase 5 only — leave empty until real trading
POLY_PRIVATE_KEY: Final[str] = os.getenv("POLY_PRIVATE_KEY", "")

# === Storage ===
DATA_DIR: Final[str] = os.getenv("DATA_DIR", "data")
