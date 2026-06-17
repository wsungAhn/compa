"""Gamma API — market list and metadata.

DO:  populate 'category' on every Market (drives fee selection and reward scoring)
     paginate fully; retry with exponential backoff
DON'T: return resolved/closed markets to callers
        make network calls inside filter functions
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from config import GAMMA_API_BASE

_log = logging.getLogger(__name__)
_BACKOFF = [2, 4, 8, 16]


@dataclass
class Market:
    market_id: str
    question: str
    outcomes: list[str]
    token_ids: list[str]
    volume_24h: float
    liquidity: float
    end_date: str
    category: str
    best_bid: float = 0.0
    best_ask: float = 1.0
    spread: float = 1.0
    cluster_id: str = ""  # "event:<id>" for cluster exposure grouping

    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2


async def _get(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> Any:
    for i, delay in enumerate([0] + _BACKOFF):
        if delay:
            await asyncio.sleep(delay)
        try:
            r = await client.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            if i == len(_BACKOFF):
                raise
            _log.warning("Gamma GET failed (%s), retry %d", exc, i + 1)


async def fetch_markets(limit: int = 100, active_only: bool = True) -> list[Market]:
    """Return open, non-resolved markets from Gamma API."""
    results: list[Market] = []
    offset = 0
    async with httpx.AsyncClient(base_url=GAMMA_API_BASE) as client:
        while True:
            data = await _get(client, "/markets", {
                "limit": limit, "offset": offset,
                "active": "true" if active_only else "false",
                "closed": "false",
            })
            if not data:
                break
            for m in data:
                cat = (m.get("category") or "other").lower()
                results.append(Market(
                    market_id=str(m.get("id", "")),
                    question=m.get("question", ""),
                    outcomes=m.get("outcomes") or [],
                    token_ids=m.get("clobTokenIds") or m.get("token_ids") or [],
                    volume_24h=float(m.get("volume24hr") or m.get("volume_24h") or 0),
                    liquidity=float(m.get("liquidity") or 0),
                    end_date=m.get("endDate") or m.get("end_date") or "",
                    category=cat,
                    cluster_id=f"event:{m.get('eventId') or ''}",
                ))
            if len(data) < limit:
                break
            offset += limit
    return results
