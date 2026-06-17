"""CLOB API — L2 orderbook depth + best bid/ask + trade ticks.

DO:  remain read-only in phases 1–4
     store top-N depth levels per side (needed by queue position model)
     preserve timestamps on every record
DON'T: activate order creation/cancellation before Phase 5
        depend on archived py-clob-client
"""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from config import CLOB_API_BASE

_log = logging.getLogger(__name__)
_BACKOFF = [2, 4, 8, 16]
DEPTH_LEVELS = 5


@dataclass
class OrderLevel:
    price: float
    size: float


@dataclass
class OrderBook:
    token_id: str
    timestamp: float
    bids: list[OrderLevel] = field(default_factory=list)  # desc by price
    asks: list[OrderLevel] = field(default_factory=list)  # asc by price
    best_bid: float = 0.0
    best_ask: float = 1.0

    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid

    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2


@dataclass
class TradeTick:
    token_id: str
    timestamp: float
    price: float
    size: float
    side: str  # "BUY" | "SELL"


async def _get(client: httpx.AsyncClient, path: str, params: dict[str, Any] | None = None) -> Any:
    for i, delay in enumerate([0] + _BACKOFF):
        if delay:
            await asyncio.sleep(delay)
        try:
            r = await client.get(path, params=params or {}, timeout=30)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            if i == len(_BACKOFF):
                raise
            _log.warning("CLOB GET %s failed (%s), retry %d", path, exc, i + 1)


async def fetch_orderbook(token_id: str, *, timestamp: float) -> OrderBook:
    async with httpx.AsyncClient(base_url=CLOB_API_BASE) as client:
        data = await _get(client, "/book", {"token_id": token_id})

    def parse(raw: list[dict[str, Any]]) -> list[OrderLevel]:
        return [OrderLevel(float(lv["price"]), float(lv["size"])) for lv in (raw or [])]

    bids = sorted(parse(data.get("bids", [])), key=lambda lv: -lv.price)[:DEPTH_LEVELS]
    asks = sorted(parse(data.get("asks", [])), key=lambda lv:  lv.price)[:DEPTH_LEVELS]
    return OrderBook(
        token_id=token_id, timestamp=timestamp,
        bids=bids, asks=asks,
        best_bid=bids[0].price if bids else 0.0,
        best_ask=asks[0].price if asks else 1.0,
    )


async def fetch_recent_trades(token_id: str, *, limit: int = 50) -> list[TradeTick]:
    """REST fallback for trade ticks (WebSocket preferred for live)."""
    async with httpx.AsyncClient(base_url=CLOB_API_BASE) as client:
        data = await _get(client, "/trades", {"token_id": token_id, "limit": limit})
    return [
        TradeTick(
            token_id=token_id,
            timestamp=float(t.get("timestamp") or time.time()),
            price=float(t.get("price") or 0),
            size=float(t.get("size") or 0),
            side=str(t.get("side") or "BUY"),
        )
        for t in (data or [])
    ]
