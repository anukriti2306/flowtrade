"""
Day 4: same pipeline as day 3, now with every fill persisted to
PostgreSQL. Strategy, ExecutionEngine, and DataEngine are completely
unchanged - PersistenceService is bolted on independently.
"""

import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from engine.bus import EventBus
from engine.data_engine import HistoricalDataEngine
from engine.strategy import MovingAverageCrossStrategy
from engine.execution import ExecutionEngine
from engine.persistence import PersistenceService
from engine.db import init_db, async_session, BacktestRun


async def create_run(symbol: str, strategy_name: str, start: datetime, end: datetime) -> int:
    """Create the parent 'backtest_runs' row first, so every fill
    below can be linked to it via run_id."""
    async with async_session() as session:
        run = BacktestRun(
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=start,
            end_date=end,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.id


async def main():
    await init_db()

    symbol = "AAPL"
    start = datetime(2025, 1, 1)
    end = datetime(2025, 6, 1)

    run_id = await create_run(symbol, "MovingAverageCross(5,20)", start, end)
    print(f"Created backtest run #{run_id}")

    bus = EventBus()

    strategy = MovingAverageCrossStrategy(bus, short_window=5, long_window=20)
    execution = ExecutionEngine(bus, slippage_pct=0.001)
    persistence = PersistenceService(bus, run_id=run_id)
    data_engine = HistoricalDataEngine(bus, symbol=symbol, start=start, end=end, replay_delay=0.02)

    await strategy.register()
    await execution.register()
    await persistence.register()

    bus_task = asyncio.create_task(bus.run())
    await data_engine.run()

    # Wait until every event currently in the queue has been fully
    # processed - including any DB commits triggered by handlers -
    # instead of guessing with a fixed sleep. A fixed sleep is a race
    # condition: if a handler's async work takes longer than the
    # sleep, you silently lose data with no error at all.
    await bus._queue.join()
    bus_task.cancel()

    print(f"\nFinal position: {strategy.position}")
    print(f"Run #{run_id} complete - fills saved to database.")


if __name__ == "__main__":
    asyncio.run(main())