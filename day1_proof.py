"""
Day 1 proof of concept.

No Strategy, no ExecutionEngine, no database yet - deliberately.
The only goal today: prove that events flow through the bus, in
order, and that a handler can react to them. Everything else in
the project builds on top of this working correctly.
"""

import asyncio
from datetime import datetime, timedelta

from engine.bus import EventBus
from engine.events import TickEvent


async def print_tick(event: TickEvent):
    """A fake 'handler' - stands in for where a real Strategy will
    plug in later. All it does today is prove it gets called, in
    order, for every tick published."""
    print(f"[{event.timestamp.time()}] {event.symbol} price = {event.price}")


async def fake_data_engine(bus: EventBus):
    """Stands in for the real DataEngine that will later read from
    a CSV. For now it just publishes 5 fake ticks with increasing
    timestamps and prices, then stops."""
    base_time = datetime(2026, 7, 19, 9, 15, 0)
    prices = [2840.0, 2841.5, 2839.0, 2845.0, 2850.5]

    for i, price in enumerate(prices):
        tick = TickEvent(
            timestamp=base_time + timedelta(seconds=i),
            symbol="RELIANCE",
            price=price,
        )
        await bus.publish(tick)
        await asyncio.sleep(0.1)  # simulate ticks arriving over time


async def main():
    bus = EventBus()
    bus.subscribe(TickEvent, print_tick)

    # Run the event loop and the fake data engine concurrently.
    # The bus.run() loop waits for events; fake_data_engine produces them.
    bus_task = asyncio.create_task(bus.run())
    await fake_data_engine(bus)

    # Give the bus a moment to drain the last event, then stop.
    await asyncio.sleep(0.2)
    bus_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
