# polypoly — Polymarket Paper Market Maker

Paper-trading bot to validate a Polymarket maker strategy before risking real capital.

Four gating phases — only advance when the current phase's data answers its question:

1. **Data collection** — market list, L2 depth, trade ticks, reward-band resting depth
2. **Paper quote engine** — virtual bid/ask, dynamic width, position tracking
3. **Paper fill / PnL** — conservative queue-aware fill model, net PnL (fees deducted)
4. **Reward scoring** — competitive denominator estimation, capital-scenario comparison

Real orders are never placed until all four questions in §0 of the v2 plan are answered with paper data.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env  # fill in API base URLs
```

## Run

```bash
python main.py --phase 1          # data collection
python main.py --phase 1 --replay # replay from saved data
```

## Key design constraints

- **Conservative fill model**: `fill = max(0, traded_through_price - queue_ahead) * haircut(0.6)`
- **Mark at post-trade mid** (not fill price) to surface adverse selection
- **All PnL is net** — taker fees deducted when liquidating inventory
- **Pre-trade risk checks** — position, exposure, cluster limits enforced before any order
- **Read-only until Phase 5** — no order creation/cancellation code active
- **`py-clob-client` is archived** (2026-05-11); uses REST + future `py-sdk` for live trading

## Statistical transition gate (§9.2)

Do NOT transition to live trading until:
- ≥ 300 paper fills
- Per-trade net PnL 95% CI lower bound > 0
- max_drawdown ≤ 3–5% of capital
- Benchmark ('do nothing', 'reward-only') comparison shows genuine edge

## Directory structure

```
config.py          # all tunable params — fees, limits, strategy
main.py            # orchestrator (--phase 1|2|3|4)
src/
  clock.py         # live/replay abstraction (same code path for both)
  fees.py          # 2026 fee table + net PnL helpers
  gamma_client.py  # market list + metadata
  clob_client.py   # L2 depth + trade ticks (read-only)
  ws_client.py     # real-time trades WebSocket feed
  market_filter.py # pure filter + scoring functions
  strategy.py      # quote generation (dynamic width)
  paper_engine.py  # conservative fill estimation
  portfolio.py     # positions, MTM, resolution
  reward_scoring.py# reward candidate ranking
  risk.py          # pre-trade checks + dynamic limits
  storage.py       # parquet + CSV writers
  logger.py        # logging setup
data/              # parquet + CSV output (gitignored except .gitkeep)
tests/             # pytest suite for core modules
notebooks/         # analysis.ipynb
```
