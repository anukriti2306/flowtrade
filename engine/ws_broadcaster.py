"""
WebSocketBroadcaster.

A third independent subscriber to the event bus, alongside Strategy
and PersistenceService - same pattern as PersistenceService, just
forwarding events to connected WebSocket clients instead of a
database. Neither Strategy, ExecutionEngine, nor PersistenceService
need to know this exists.

This object is created ONCE, at module load time, and persists across
live runs - only the bus it listens to is swapped via attach() when a
new live run starts. This matters: a browser can connect to /ws/live
before a live run has even been started, and its connection must
still be usable once a run does start - if a new broadcaster instance
were created per run, any WebSocket that connected earlier would be
silently orphaned, listening to an object nothing broadcasts through
anymore.
"""

import json
from fastapi import WebSocket

from engine.bus import EventBus
from engine.events import TickEvent, OrderEvent, FillEvent


class WebSocketBroadcaster:
    def __init__(self, bus: EventBus | None = None):
        self.bus = bus
        self.connections: list[WebSocket] = []

    def attach(self, bus: EventBus):
        """Point this broadcaster at a new bus for a new live run,
        without losing already-connected WebSocket clients."""
        self.bus = bus

    async def register(self):
        self.bus.subscribe(TickEvent, self._on_tick)
        self.bus.subscribe(OrderEvent, self._on_order)
        self.bus.subscribe(FillEvent, self._on_fill)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def _broadcast(self, payload: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def _on_tick(self, event: TickEvent):
        await self._broadcast({
            "type": "tick",
            "symbol": event.symbol,
            "price": event.price,
            "timestamp": event.timestamp.isoformat(),
        })

    async def _on_order(self, event: OrderEvent):
        await self._broadcast({
            "type": "order",
            "symbol": event.symbol,
            "side": event.side,
            "quantity": event.quantity,
            "timestamp": event.timestamp.isoformat(),
        })

    async def _on_fill(self, event: FillEvent):
        await self._broadcast({
            "type": "fill",
            "symbol": event.symbol,
            "side": event.side,
            "quantity": event.quantity,
            "fill_price": event.fill_price,
            "timestamp": event.timestamp.isoformat(),
        })