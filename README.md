# flowtrade

A small event-driven backtesting engine, built to understand a specific
architectural idea deeply: **the same strategy code can run against both
historical data (backtest) and simulated live data (paper trading),
because the strategy never talks to a data source directly — it only
ever reacts to events on a shared bus.**

## Why this exists

Most simple backtesters loop over a DataFrame of historical prices,
calling a function for each row. That's fine for a quick script, but it
doesn't reflect how a real trading system has to work — a real system
can't loop over the future, it has to react to events as they arrive,
in order, one at a time.

This project is a deliberately small, from-scratch implementation of
that event-driven pattern, built to understand it properly rather than
just use a library that already does it.

## Inspiration & attribution

This project's core architectural idea — a unified strategy interface
that runs unmodified across backtest and live execution, driven by an
event bus rather than direct function calls — is inspired by
[NautilusTrader](https://github.com/nautechsystems/nautilus_trader), an
open-source, production-grade algorithmic trading platform written in
Rust and Python.

flowtrade is an independent, from-scratch, educational implementation
of a small subset of that idea. It is not affiliated with, endorsed by,
or built using any code from Nautech Systems or NautilusTrader.

## Architecture

```
DataEngine (historical replay, or later: Redis live feed)
        |
        v
   EventBus  <-- single asyncio queue, processes one event at a time
        |
        v
   Strategy  (reacts to TickEvent, emits OrderEvent)
        |
        v
ExecutionEngine (simulates fills, emits FillEvent)
        |
        v
   Strategy  (reacts to FillEvent, e.g. updates position)
```

Events are processed strictly in order — a tick's full consequences
(including any resulting order and fill) are resolved before the next
tick is even looked at. This preserves causality, which is what makes
the backtest results trustworthy.

## Status

Day 1 — core `Event` types and `EventBus` built and verified. Ticks flow
through the bus in order and reach a handler correctly. Strategy and
execution engine not yet implemented.

## Stack

Python (asyncio) for the core engine. FastAPI, PostgreSQL (async
SQLAlchemy), and Redis planned for the API layer, persistence, and live
feed simulation respectively.
