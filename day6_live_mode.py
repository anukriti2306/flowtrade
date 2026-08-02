"""
Day 6: live paper-trading mode. Same Strategy, ExecutionEngine, and
PersistenceService as every previous day - only the data source has
changed, from HistoricalDataEngine to LiveDataEngine. This is the
actual proof of backtest/live parity: run simulate_live_feed.py in a
separate terminal first, then run this.
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from engine.bus import EventBus
from engine.live_data_engine import LiveDataEngine
from engine.strategy import MovingAverageCrossStrategy
from engine.execution import ExecutionEngine
from engine.persistence import PersistenceService
from engine.db import init_db, async_session, BacktestRun
from datetime import datetime


async def create_run(symbol: str, strategy_name: str) -> int:
    async with async_session() as session:
        run = BacktestRun(
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run.id


async def main():
    await init_db()

    run_id = await create_run("AAPL", "MovingAverageCross(5,20)-LIVE")
    print(f"Created live run #{run_id}. Ctrl+C to stop.")

    bus = EventBus()

    strategy = MovingAverageCrossStrategy(bus, short_window=5, long_window=20)
    execution = ExecutionEngine(bus, slippage_pct=0.001)
    persistence = PersistenceService(bus, run_id=run_id)
    data_engine = LiveDataEngine(bus)

    await strategy.register()
    await execution.register()
    await persistence.register()

    bus_task = asyncio.create_task(bus.run())

    try:
        await data_engine.run()  # runs forever until Ctrl+C
    except KeyboardInterrupt:
        pass
    finally:
        await bus._queue.join()
        bus_task.cancel()
        print(f"\nLive run #{run_id} stopped.")


if __name__ == "__main__":
    asyncio.run(main())