"""
PersistenceService.

Subscribes to FillEvent, same as Strategy does with on_fill(). Its only
job is saving completed trades to the database. It has no idea what
strategy generated the trade, no idea what the DataEngine's source
was - it just reacts to the fact that a trade happened.

This is the event-driven pattern doing real work: Strategy and
PersistenceService both react to the exact same FillEvent, completely
unaware of each other.
"""

from engine.bus import EventBus
from engine.events import FillEvent
from engine.db import async_session, Fill


class PersistenceService:
    def __init__(self, bus: EventBus, run_id: int):
        self.bus = bus
        self.run_id = run_id

    async def register(self):
        self.bus.subscribe(FillEvent, self.on_fill)

    async def on_fill(self, event: FillEvent):
        """Write the fill to the database. Uses its own short-lived
        session per write - simple and safe for this scale. A
        higher-throughput system might batch writes instead, but one
        write per fill is fine for a backtest engine."""
        async with async_session() as session:
            fill = Fill(
                run_id=self.run_id,
                symbol=event.symbol,
                side=event.side,
                quantity=event.quantity,
                fill_price=event.fill_price,
                timestamp=event.timestamp,
            )
            session.add(fill)
            await session.commit()