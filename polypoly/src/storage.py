"""Storage helpers — parquet (depth, trades, band_depth) + CSV (paper_trades, summary).

DO:
  store L2 depth + trade ticks + band_depth from Phase 1 (fill model depends on all three)
  snapshot market_config at collection time for reproducibility

DON'T:
  store only best bid/ask (depth and trades are mandatory for the fill model)
  skip config snapshots (fee/reward params change; must be reproducible)
"""
from __future__ import annotations
import csv
import time
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from config import DATA_DIR


def _dir() -> Path:
    p = Path(DATA_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _append_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    if not HAS_PANDAS or not rows:
        return
    df_new = pd.DataFrame(rows)
    if path.exists():
        pd.concat([pd.read_parquet(path), df_new], ignore_index=True).to_parquet(path, index=False)
    else:
        df_new.to_parquet(path, index=False)


def append_orderbook_snapshot(rows: list[dict[str, Any]]) -> None:
    _append_parquet(_dir() / "orderbook_snapshots.parquet", rows)


def append_trades(rows: list[dict[str, Any]]) -> None:
    _append_parquet(_dir() / "trades.parquet", rows)


def append_band_depth(rows: list[dict[str, Any]]) -> None:
    _append_parquet(_dir() / "band_depth.parquet", rows)


def snapshot_market_config(config_dict: dict[str, Any]) -> None:
    _append_parquet(_dir() / "market_config_snapshots.parquet",
                    [{**config_dict, "snapshot_ts": time.time()}])


_PAPER_COLS = [
    "timestamp", "market_id", "token_id", "side", "price", "size_usdc",
    "fill_qty_conservative", "fill_qty_aggressive", "fill_qty_decision",
    "mark_price", "net_pnl", "category",
]


def append_paper_trade(row: dict[str, Any]) -> None:
    path = _dir() / "paper_trades.csv"
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_PAPER_COLS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerow(row)


_SUMMARY_COLS = [
    "date", "total_pnl_net", "realized_pnl", "unrealized_pnl", "resolution_pnl",
    "reward_earned", "rebate_earned", "fill_count", "fill_rate",
    "avg_spread_captured_net", "per_trade_pnl_mean", "per_trade_pnl_std",
    "per_trade_pnl_ci95_lo", "max_drawdown", "inventory_imbalance", "active_markets",
]


def append_daily_summary(row: dict[str, Any]) -> None:
    path = _dir() / "daily_summary.csv"
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_SUMMARY_COLS, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerow(row)
