# flowtrade

A small event-driven trading engine, built to understand one architectural idea deeply: **the same strategy code runs unmodified against both historical data (backtest) and a live price feed (paper trading), because the strategy never talks to a data source directly - it only reacts to events on a shared bus.**

## Why this exists

Most simple backtesters loop over a DataFrame of historical prices, calling a function for each row. That's fine for a quick script, but it doesn't reflect how a real trading system has to work - a real system can't loop over the future, it has to react to events as they arrive, in order, one at a time, and the exact same reaction logic has to work whether that data is history or happening right now.

This project is a deliberately small, from-scratch implementation of that pattern, built to prove it rather than just use a library that already does it.

## Inspiration & attribution

This project's core architectural idea - a unified strategy interface that runs unmodified across backtest and live execution, driven by an event bus rather than direct function calls - is inspired by [NautilusTrader](https://github.com/nautechsystems/nautilus_trader), an open-source, production-grade algorithmic trading platform written in Rust and Python.

flowtrade is an independent, from-scratch, educational implementation of a small subset of that idea. It is not affiliated with, endorsed by, or built using any code from Nautech Systems or NautilusTrader.

## The proof: zero lines changed

The single most important fact about this project: when live paper-trading mode was added, **`Strategy`, `ExecutionEngine`, and `PersistenceService` required zero code changes.** Only a new `LiveDataEngine` was added, publishing the same `TickEvent` shape onto the same bus. This was verified directly - the exact same strategy class that traded 102 days of real historical AAPL data also correctly traded a simulated live feed over Redis pub/sub, with identical signal generation, slippage-adjusted fills, and persistence behavior.

## Architecture

Two interchangeable data sources feed the same pipeline:

- HistoricalDataEngine (Alpaca) -> EventBus
- LiveDataEngine (Redis pub/sub) -> EventBus

From there, every event flows through one path:

EventBus (single asyncio queue, one event at a time)
-> Strategy (reacts to TickEvent, emits OrderEvent)
-> ExecutionEngine (simulates fills with slippage, emits FillEvent)
-> Strategy (on_fill: updates position) AND PersistenceService (on_fill: writes to PostgreSQL), independently

Events are processed strictly in order - a tick's full consequences (including any resulting order and fill) are resolved before the next tick is even looked at. This preserves causality, which is what makes backtest results trustworthy, and is exactly what allows the two very different data sources above to be interchangeable.

## What's built

**Core engine**
- `EventBus` - single asyncio queue, strictly sequential processing, pub/sub-style handler registration per event type
- `Strategy` (abstract) / `MovingAverageCrossStrategy` - reacts to `TickEvent`, emits `OrderEvent`, updates position on `FillEvent`
- `ExecutionEngine` - simulates fills with a slippage model, emits `FillEvent`

**Data sources (interchangeable, zero Strategy changes between them)**
- `HistoricalDataEngine` - replays real historical daily bars from Alpaca's Market Data API (paper trading keys, US equities)
- `LiveDataEngine` - subscribes to a Redis pub/sub channel and forwards messages as `TickEvent`s. Paired with `simulate_live_feed.py`, a deliberately *separate* process that publishes a simulated live feed - honestly mirroring how a real live feed comes from an external exchange, not from inside the trading engine itself

**Persistence & metrics**
- `PersistenceService` - subscribes to `FillEvent` independently of `Strategy`; every run creates a `backtest_runs` row, every fill persists to a linked `fills` table via async SQLAlchemy
- `compute_metrics()` - pairs consecutive fills into round-trip trades and computes total return, win rate, max drawdown, and an equity curve. The pure P&L/drawdown math is isolated from the database query (`_compute_from_fills`) specifically so it's unit-testable without a live database connection

**API**
- `POST /backtest` - triggers a backtest as a FastAPI `BackgroundTask`, returns a `run_id` immediately rather than blocking on the full replay
- `GET /backtest/{run_id}` - run metadata plus computed metrics (null if the run hasn't produced enough fills yet)
- `GET /backtest/{run_id}/equity-curve` - equity curve as a point series, for charting

**Tests**
- `tests/test_metrics.py` - unit tests on the pure P&L logic: winning/losing long trades, short-trade P&L direction (the branch most likely to have a sign error), equity curve correctness, max drawdown detection, and edge cases around unmatched/odd fill counts

## Notable bugs hit and fixed along the way

Kept here deliberately, since debugging real issues is as much a part of this project as the features:

1. **Shutdown race condition** - originally used a fixed `asyncio.sleep()` before cancelling the event loop after a run finished. If a handler's async work (like a database commit) took longer than the sleep, the task was cancelled mid-write with no error - fills silently never made it to the database despite a "success" printed to console. Fixed by awaiting `queue.join()`, which only returns once every event's full handler chain, including downstream async work, has actually completed.

2. **Timezone-aware vs naive datetime mismatch** - Alpaca returns UTC timezone-aware timestamps; the database's `TIMESTAMP` column is timezone-naive. Every insert failed with `can't subtract offset-naive and offset-aware datetimes`. Fixed by stripping `tzinfo` at the exact boundary where data enters the pipeline, while keeping the underlying value correctly in UTC throughout - timestamps stay UTC internally everywhere; conversion to local time, if wanted, only happens at the display/print layer, never inside the pipeline itself.

## Stack

Python (asyncio) for the core engine. Alpaca (`alpaca-py`) for historical market data. Redis (via Upstash) for the live feed simulation. PostgreSQL + async SQLAlchemy (`asyncpg`) for persistence. FastAPI for the API layer. pytest for unit tests.

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create a `.env` file (never committed - see `.gitignore`):
```bash
APCA_API_KEY_ID=your_alpaca_paper_key
APCA_API_SECRET_KEY=your_alpaca_paper_secret
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/flowtrade
REDIS_URL=rediss://default:password@your-db.upstash.io:6379
```

Create the database once:

```sql
CREATE DATABASE flowtrade;
```

**Run a backtest against real historical data:**

```bash
python day4_persistence.py
python day5_metrics.py     # then enter the run_id it produced
```

**Run the API:**

```bash
uvicorn api.main:app --reload
```

Then open `http://127.0.0.1:8000/docs` for the interactive API.

**Run live paper-trading mode (two terminals):**

```bash
# Terminal 1 - simulates the exchange
python simulate_live_feed.py

# Terminal 2 - the actual engine, subscribing
python day6_live_mode.py
```

**Run tests:**

```bash
pytest tests/ -v
```

## Proposed Future Enhancements
- Frontend/dashboard for visualizing results
- Real order book simulation (L2 depth) - fills use last-price + slippage only
- Multi-symbol or multi-venue support
- Actual connection to a real brokerage for live trading - this project only ever touches paper trading / simulated data, no real money at any point
