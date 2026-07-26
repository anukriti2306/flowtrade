"""
Day 2: full event flow, tick -> strategy -> order -> fill -> strategy.
Still using fake data - real historical data replay comes in day 3.
"""

import asyncio
from datetime import datetime, timedelta

from engine.bus import EventBus
from engine.events import TickEvent
from engine.strategy import MovingAverageCrossStrategy
from engine.execution import ExecutionEngine


async def fake_data_engine(bus: EventBus):
    base_time = datetime(2026, 7, 19, 9, 15, 0)
    # Prices trend down then up, to trigger both a SELL and a BUY signal
    prices = [2850, 2845, 2840, 2835, 2830, 2828, 2832, 2838, 2845, 2852, 2860, 2868]

    for i, price in enumerate(prices):
        tick = TickEvent(
            timestamp=base_time + timedelta(seconds=i),
            symbol="RELIANCE",
            price=float(price),
        )
        await bus.publish(tick)
        await asyncio.sleep(0.1)


async def main():
    bus = EventBus()

    strategy = MovingAverageCrossStrategy(bus, short_window=3, long_window=6)
    execution = ExecutionEngine(bus, slippage_pct=0.001)

    await strategy.register()
    await execution.register()

    bus_task = asyncio.create_task(bus.run())
    await fake_data_engine(bus)

    await asyncio.sleep(0.3)
    bus_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())