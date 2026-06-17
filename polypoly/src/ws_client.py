"""WebSocket client — real-time trades feed (primary) + book updates.

DO:  adopt trades feed in Phase 1 (not deferred to v0.2)
     handle reconnect and sequence gaps
DON'T: use 10s REST snapshots as the sole source of fill detection
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from collections.abc import Callable

from src.clob_client import TradeTick
from config import CLOB_WS_BASE

_log = logging.getLogger(__name__)

try:
    from websockets import connect as _ws_connect  # type: ignore[import-untyped]
    HAS_WS = True
except ImportError:
    HAS_WS = False


async def stream_trades(
    token_ids: list[str],
    on_tick: Callable[[TradeTick], None],
    *,
    reconnect_delay: float = 3.0,
) -> None:
    """Subscribe to live trades channel; call on_tick for each fill.

    Runs indefinitely — wrap in asyncio.create_task() and cancel to stop.
    """
    if not HAS_WS:
        _log.warning("websockets not installed — trade streaming unavailable")
        return

    sub = json.dumps({
        "type": "subscribe",
        "channel": "live_activity",
        "assets_ids": token_ids,
    })

    while True:
        try:
            async with _ws_connect(CLOB_WS_BASE, ping_interval=20) as ws:  # type: ignore[attr-defined]
                await ws.send(sub)
                _log.info("WS subscribed to %d tokens", len(token_ids))
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        events = msg if isinstance(msg, list) else [msg]
                        for ev in events:
                            if ev.get("type") != "trade":
                                continue
                            on_tick(TradeTick(
                                token_id=str(ev.get("asset_id") or ""),
                                timestamp=float(ev.get("timestamp") or time.time()),
                                price=float(ev.get("price") or 0),
                                size=float(ev.get("size") or 0),
                                side=str(ev.get("side") or "BUY"),
                            ))
                    except Exception:
                        _log.debug("WS parse error", exc_info=True)
        except Exception as exc:
            _log.warning("WS disconnected (%s), reconnecting in %.1fs", exc, reconnect_delay)
            await asyncio.sleep(reconnect_delay)
