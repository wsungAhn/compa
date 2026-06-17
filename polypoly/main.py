"""Entry point — 4-phase paper MM orchestrator.

Phase 1: data collection (markets, L2 depth, trade ticks, band depth)
Phase 2: paper quote engine
Phase 3: paper fill / PnL tracking
Phase 4: reward candidate scoring

Real orders are never placed until the 4 questions in §0 of the v2 plan
are answered with paper data and the statistical gate in §9.2 is passed.

Usage:
  python main.py --phase 1
  python main.py --phase 1 --replay
"""
from __future__ import annotations
import argparse
import asyncio
import logging
import time

from src.clock import LiveClock
from src.gamma_client import fetch_markets
from src.clob_client import fetch_orderbook, fetch_recent_trades
from src.market_filter import filter_markets
from src.storage import append_orderbook_snapshot, append_trades, snapshot_market_config
from src.logger import setup_logging
import config as cfg

_log = logging.getLogger(__name__)


async def phase1_collect() -> None:
    _log.info("Phase 1: fetching market list")
    markets = await fetch_markets()
    _log.info("Fetched %d markets", len(markets))

    now = time.time()
    candidates = filter_markets(markets, now)
    _log.info("Filtered to %d candidates", len(candidates))

    snapshot_market_config({
        "taker_fees": cfg.TAKER_FEES,
        "maker_rebate": cfg.MAKER_REBATE,
        "fill_haircut": cfg.FILL_HAIRCUT,
    })

    for fm in candidates:
        market = fm.market
        token_id = market.token_ids[0] if market.token_ids else ""
        if not token_id:
            continue
        try:
            ob = await fetch_orderbook(token_id, timestamp=time.time())
            append_orderbook_snapshot([{
                "timestamp": ob.timestamp,
                "market_id": market.market_id,
                "token_id": ob.token_id,
                "best_bid": ob.best_bid,
                "best_ask": ob.best_ask,
                "spread": ob.spread,
                "mid": ob.mid,
                "category": market.category,
                "bids_json": str([(lv.price, lv.size) for lv in ob.bids]),
                "asks_json": str([(lv.price, lv.size) for lv in ob.asks]),
            }])
            trades = await fetch_recent_trades(token_id, limit=50)
            if trades:
                append_trades([{
                    "timestamp": t.timestamp, "market_id": market.market_id,
                    "token_id": t.token_id, "price": t.price,
                    "size": t.size, "side": t.side,
                } for t in trades])
        except Exception:
            _log.warning("Collection failed for %s", market.market_id, exc_info=True)

    _log.info("Phase 1 complete — %d candidates", len(candidates))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3, 4])
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.phase == 1:
        await phase1_collect()
    else:
        _log.info("Phase %d not yet implemented — run phase 1 first", args.phase)


if __name__ == "__main__":
    asyncio.run(main())
