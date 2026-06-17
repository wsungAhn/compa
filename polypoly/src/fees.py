"""Category fee table + net PnL helpers.

Single source of truth for all fee/rebate arithmetic.
DON'T re-implement fee logic in other modules.
"""
from __future__ import annotations
from config import TAKER_FEES, MAKER_REBATE


def taker_fee(category: str) -> float:
    return TAKER_FEES.get(category.lower(), TAKER_FEES["other"])


def net_spread(gross_spread: float, category: str) -> float:
    """Gross spread minus taker fee paid to liquidate one side via market order."""
    return gross_spread - taker_fee(category)


def fee_adjusted_edge(bid: float, ask: float, category: str) -> float:
    """(ask - bid) - 2 * taker_fee.  Positive means spread covers round-trip fees."""
    return (ask - bid) - 2 * taker_fee(category)


def maker_rebate() -> float:
    return MAKER_REBATE
