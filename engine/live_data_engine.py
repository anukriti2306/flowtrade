"""
LiveDataEngine - subscribes to a Redis channel and publishes TickEvents
onto the bus, exactly like HistoricalDataEngine does with historical
data. Strategy, ExecutionEngine, and PersistenceService require ZERO
changes to work with this - they only ever see TickEvents, and never
know or care where they came from.
"""

import json
import os
from datetime import datetime
import redis.asyncio as redis

from engine.bus import EventBus
from engine.events import TickEvent

CHANNEL = "flowtrade:live_ticks"


class LiveDataEngine:
    def __init__(self, bus: EventBus):
        self.bus = bus
        redis_url = os.environ["REDIS_URL"]
        self.client = redis.from_url(redis_url)

    async def run(self):
        """Subscribe and forward every message as a TickEvent. Runs
        forever - unlike HistoricalDataEngine.run(), which finishes
        once historical data is exhausted, a live feed never 'ends'
        on its own."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(CHANNEL)
        print(f"Subscribed to '{CHANNEL}', waiting for live ticks...")

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue  # skip the subscription confirmation message

            data = json.loads(message["data"])
            tick = TickEvent(
                timestamp=datetime.fromisoformat(data["timestamp"]).replace(tzinfo=None),
                symbol=data["symbol"],
                price=data["price"],
            )
            await self.bus.publish(tick)