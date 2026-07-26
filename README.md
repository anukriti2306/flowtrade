# flowtrade

A small event-driven backtesting engine, built to understand a specific architectural idea deeply: **the same strategy code can run against both historical data (backtest) and simulated live data (paper trading), because the strategy never talks to a data source directly - it only ever reacts to events on a shared bus.**

## Why this exists

Most simple backtesters loop over a DataFrame of historical prices, calling a function for each row. That's fine for a quick script, but it doesn't reflect how a real trading system has to work - a real system can't loop over the future, it has to react to events as they arrive, in order, one at a time.

This project is a deliberately small, from-scratch implementation of that event-driven pattern, built to understand it properly rather than just use a library that already does it.

## Inspiration & attribution

This project's core architectural idea - a unified strategy interface that runs unmodified across backtest and live execution, driven by an event bus rather than direct function calls - is inspired by [NautilusTrader](https://github.com/nautechsystems/nautilus_trader), an open-source, production-grade algorithmic trading platform written in Rust and Python.

flowtrade is an independent, from-scratch, educational implementation of a small subset of that idea. It is not affiliated with, endorsed by, or built using any code from Nautech Systems or NautilusTrader.

## Architecture

    HistoricalDataEngine (Alpaca Market Data API)
            |
            v
       EventBus  <-- single asyncio queue, processes one event at a time
            |
            v
       Strategy  (reacts to TickEvent, emits OrderEvent)
            |
            v
    ExecutionEngine (simulates fills with slippage, emits FillEvent)
            |
            v
       ---------------------------
       |                         |
       v                         v
    Strategy (on_fill)    PersistenceService (on_fill)
    (updates position)    (writes to PostgreSQL)

Events are processed strictly in order - a tick's full consequences (including any resulting order and fill) are resolved before the next tick is even looked at. This preserves causality, which is what makes the backtest results trustworthy.

`Strategy` and `PersistenceService` both subscribe independently to `FillEvent`, unaware of each other - this is the event-driven pattern doing real work: new functionality (persistence) was added without modifying `ExecutionEngine` or `Strategy` at all.

## Status

**Day 4 complete.**

- **Day 1** - Core `Event` types and `EventBus` built. Verified ticks flow through the bus in order and reach a handler correctly.
- **Day 2** - `Strategy` abstract interface and `MovingAverageCrossStrategy` implemented. `ExecutionEngine` added, simulating fills with a slippage model. Full flow verified: tick -> signal -> order -> fill -> position update, using fake price data.
- **Day 3** - Replaced fake data with real historical daily bars from Alpaca's Market Data API (US equities, paper trading keys). Verified end-to-end against real AAPL data - the `Strategy` class required zero changes when the data source was swapped, which is the entire point of the event-driven design.
- **Day 4** - Added `PersistenceService`, subscribing to `FillEvent` independently of `Strategy`. Every backtest run creates a `backtest_runs` row in PostgreSQL; every fill persists to a linked `fills` table via async SQLAlchemy.

  Two bugs hit and fixed during this stage, both worth noting:
  1. **Shutdown race condition** - originally used a fixed `asyncio.sleep()` before cancelling the event loop, which could cut off an in-flight database commit mid-write with no error. Fixed by awaiting `queue.join()`, which only returns once every queued event (including downstream async work like a DB commit) has fully completed.
  2. **Timezone-aware vs naive datetime mismatch** - Alpaca returns UTC timezone-aware timestamps, but the database's `TIMESTAMP` column is timezone-naive, causing every insert to fail. Fixed by stripping `tzinfo` at the boundary where data enters the pipeline (`.replace(tzinfo=None)`), while keeping the underlying value correctly in UTC throughout - timestamps are kept in UTC internally everywhere; conversion to local time, if wanted, only happens at the display/print layer, never inside the pipeline itself.

Backtest metrics (return, win rate, drawdown), FastAPI endpoints, and live paper-trading mode via Redis are not yet implemented.

## Stack

Python (asyncio) for the core engine. Alpaca (`alpaca-py`) for market data. PostgreSQL + async SQLAlchemy (`asyncpg`) for persistence. FastAPI and Redis planned for the API layer and live feed simulation.

## Setup

    python -m venv venv
    venv\Scripts\activate        # Windows
    pip install -r requirements.txt

Create a `.env` file (never committed - see `.gitignore`) with:

    APCA_API_KEY_ID=your_alpaca_paper_key
    APCA_API_SECRET_KEY=your_alpaca_paper_secret
    DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/flowtrade

Create the database once:

    CREATE DATABASE flowtrade;

Run the latest stage:

    python day4_persistence.py