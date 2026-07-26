"""
The Strategy interface.

This is the single most important file in the whole project - it's
what makes backtest/live parity possible. A Strategy only ever reacts
to events handed to it by the bus. It has no idea whether those events
came from historical replay or a live feed. That's the entire point.
"""

from abc import ABC, abstractmethod

from engine.events import TickEvent, FillEvent, OrderEvent
from engine.bus import EventBus


class Strategy(ABC):
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.position = 0  # how many shares currently held (+ve = long)

    @abstractmethod
    async def on_tick(self, event: TickEvent):
        """Called every time a new price arrives. This is where the
        actual trading logic lives - decide whether to buy, sell, or
        do nothing based on this price update."""
        raise NotImplementedError

    @abstractmethod
    async def on_fill(self, event: FillEvent):
        """Called when an order this strategy placed has actually been
        executed. Used to update internal state, like position size."""
        raise NotImplementedError

    async def register(self):
        """Wire this strategy up to the bus. Called once, at startup."""
        self.bus.subscribe(TickEvent, self.on_tick)
        self.bus.subscribe(FillEvent, self.on_fill)


class MovingAverageCrossStrategy(Strategy):
    """The simplest possible strategy: track a short and long moving
    average of price. When short crosses above long, buy. When it
    crosses below, sell. Deliberately simple - the point of this
    project is the architecture, not the strategy's cleverness."""

    def __init__(self, bus: EventBus, short_window: int = 3, long_window: int = 6):
        super().__init__(bus)
        self.short_window = short_window
        self.long_window = long_window
        self.prices: list[float] = []
        self.last_signal: str | None = None  # "BUY" or "SELL", to avoid duplicate orders

    async def on_tick(self, event: TickEvent):
        self.prices.append(event.price)

        # Not enough data yet to compute the long moving average
        if len(self.prices) < self.long_window:
            return

        short_avg = sum(self.prices[-self.short_window:]) / self.short_window
        long_avg = sum(self.prices[-self.long_window:]) / self.long_window

        if short_avg > long_avg and self.last_signal != "BUY":
            print(f"[{event.timestamp.time()}] Signal: BUY {event.symbol} @ {event.price}")
            order = OrderEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                side="BUY",
                quantity=10,
            )
            await self.bus.publish(order)
            self.last_signal = "BUY"

        elif short_avg < long_avg and self.last_signal != "SELL":
            print(f"[{event.timestamp.time()}] Signal: SELL {event.symbol} @ {event.price}")
            order = OrderEvent(
                timestamp=event.timestamp,
                symbol=event.symbol,
                side="SELL",
                quantity=10,
            )
            await self.bus.publish(order)
            self.last_signal = "SELL"

    async def on_fill(self, event: FillEvent):
        if event.side == "BUY":
            self.position += event.quantity
        else:
            self.position -= event.quantity
        print(f"  -> Filled {event.side} {event.quantity} @ {event.fill_price:.2f} | position = {self.position}")