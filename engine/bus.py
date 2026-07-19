"""
The event bus.

This is the heart of the whole system. Without it, the DataEngine would
need to directly call the Strategy, which would need to directly call
the ExecutionEngine - every component tightly wired to every other one.

Instead: components only know about the EventBus. They push events onto
it, and they register handlers to react to events they care about. The
DataEngine has never heard of the Strategy, and the Strategy has never
heard of the ExecutionEngine. This is what "decoupling" actually means -
not a buzzword, a concrete removal of direct dependencies.

Why this matters for backtest/live parity specifically: the Strategy
only ever reacts to events arriving on the bus. It has no idea whether
those events came from a DataEngine replaying history, or from a Redis
subscriber receiving live prices. Same strategy code, different event
source - because the strategy was never coupled to the source in the
first place.
"""

import asyncio
from collections import defaultdict
from typing import Callable, Type

from engine.events import Event


class EventBus:
    def __init__(self):
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._handlers: dict[Type[Event], list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: Type[Event], handler: Callable):
        """Register a handler function to be called whenever an event
        of this type arrives. A component can subscribe to multiple
        event types - e.g. a Strategy subscribes to TickEvent AND
        FillEvent, since it reacts to both."""
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event):
        """Push an event onto the queue. This is non-blocking - the
        publisher doesn't wait for the event to be processed, it just
        hands it off and moves on. This matters: the DataEngine can
        keep replaying ticks without waiting for the Strategy to
        finish reacting to the previous one."""
        await self._queue.put(event)

    async def run(self):
        """The actual event loop. Pulls one event at a time off the
        queue, finds every handler registered for that event's type,
        and calls them in order. Processing one event fully before
        picking up the next is what guarantees a fill can never be
        processed 'before' the tick that caused it - order is
        preserved because it's a single queue, drained one item at
        a time."""
        while True:
            event = await self._queue.get()
            handlers = self._handlers[type(event)]
            for handler in handlers:
                await handler(event)
            self._queue.task_done()
