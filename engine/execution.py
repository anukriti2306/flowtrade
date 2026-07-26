"""
The execution engine.

Receives OrderEvents, simulates a fill, and publishes a FillEvent.
This is where slippage gets modeled - in real trading, the price you
get filled at is rarely the exact price you saw when you decided to
trade.
"""

from engine.events import OrderEvent, FillEvent, TickEvent
from engine.bus import EventBus


class ExecutionEngine:
    def __init__(self, bus: EventBus, slippage_pct: float = 0.001):
        self.bus = bus
        self.slippage_pct = slippage_pct
        self.last_price: dict[str, float] = {}

    async def register(self):
        self.bus.subscribe(OrderEvent, self.on_order)
        self.bus.subscribe(TickEvent, self.on_tick)

    async def on_tick(self, event: TickEvent):
        """Track the most recent price per symbol - needed to know
        what price to fill an order at."""
        self.last_price[event.symbol] = event.price

    async def on_order(self, event: OrderEvent):
        """Simulate a fill. Real fills happen at the NEXT tick's price
        after an order is placed, not the price the strategy saw when
        it decided to trade - and slippage pushes the price slightly
        against you."""
        price = self.last_price.get(event.symbol)
        if price is None:
            return  # no price data yet, can't fill

        if event.side == "BUY":
            fill_price = price * (1 + self.slippage_pct)
        else:
            fill_price = price * (1 - self.slippage_pct)

        fill = FillEvent(
            timestamp=event.timestamp,
            symbol=event.symbol,
            side=event.side,
            quantity=event.quantity,
            fill_price=fill_price,
        )
        await self.bus.publish(fill)