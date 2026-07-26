"""
Day 3: real historical data via Alpaca, same strategy and execution
engine as day 2, completely unchanged.
"""

import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables - must happen
                # before HistoricalDataEngine is created

from engine.bus import EventBus
from engine.data_engine import HistoricalDataEngine
from engine.strategy import MovingAverageCrossStrategy
from engine.execution import ExecutionEngine


async def main():
    bus = EventBus()

    strategy = MovingAverageCrossStrategy(bus, short_window=5, long_window=20)
    execution = ExecutionEngine(bus, slippage_pct=0.001)
    data_engine = HistoricalDataEngine(
        bus,
        symbol="AAPL",
        start=datetime(2025, 1, 1),
        end=datetime(2025, 6, 1),
        replay_delay=0.02,
    )

    await strategy.register()
    await execution.register()

    bus_task = asyncio.create_task(bus.run())
    await data_engine.run()

    await asyncio.sleep(0.5)
    bus_task.cancel()
    print(f"\nFinal position: {strategy.position}")


if __name__ == "__main__":
    asyncio.run(main())