"""Portfolio — positions, MTM, resolution.

DO:
  mark open positions at mid (unrealized PnL)
  book resolved markets at 0 or 1 on a SEPARATE resolution_pnl line
  track cluster exposure for correlated-market risk

DON'T:
  mix resolution PnL into spread PnL (obscures source of edge)
  assume markets are independent (same event moves all legs simultaneously)
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Position:
    market_id: str
    token_id: str
    side: str    # "YES" | "NO"
    qty: float
    avg_price: float
    cluster_id: str = ""


@dataclass
class PortfolioState:
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    resolution_pnl: float = 0.0   # separate line: binary 0/1 payoff
    reward_earned: float = 0.0
    rebate_earned: float = 0.0

    def unrealized_pnl(self, mid_prices: dict[str, float]) -> float:
        total = 0.0
        for token_id, pos in self.positions.items():
            mid = mid_prices.get(token_id, pos.avg_price)
            total += pos.qty * (mid - pos.avg_price) if pos.side == "YES" else pos.qty * (pos.avg_price - mid)
        return total

    def total_exposure(self) -> float:
        return sum(p.qty * p.avg_price for p in self.positions.values())

    def cluster_exposure(self) -> dict[str, float]:
        out: dict[str, float] = defaultdict(float)
        for pos in self.positions.values():
            if pos.cluster_id:
                out[pos.cluster_id] += pos.qty * pos.avg_price
        return dict(out)

    def apply_fill(self, fill: object) -> None:
        from src.paper_engine import PaperFill
        assert isinstance(fill, PaperFill)
        order = fill.order
        token_id = order.token_id
        if token_id in self.positions:
            pos = self.positions[token_id]
            new_qty = pos.qty + fill.fill_qty
            pos.avg_price = (pos.qty * pos.avg_price + fill.fill_qty * order.price) / new_qty
            pos.qty = new_qty
        else:
            self.positions[token_id] = Position(
                market_id=order.market_id, token_id=token_id,
                side="YES" if order.side == "BID" else "NO",
                qty=fill.fill_qty, avg_price=order.price,
            )
        self.realized_pnl += fill.net_pnl

    def resolve_market(self, token_id: str, outcome: float) -> None:
        """Close at binary resolution (0.0 = NO wins, 1.0 = YES wins)."""
        if token_id not in self.positions:
            return
        pos = self.positions.pop(token_id)
        pnl = pos.qty * (outcome - pos.avg_price) if pos.side == "YES" else pos.qty * (pos.avg_price - outcome)
        self.resolution_pnl += pnl
