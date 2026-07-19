"""
Event definitions.

Everything that happens in this system - a price update, an order being
placed, an order being filled - is represented as an Event. Components
never call each other directly. They only ever emit events onto the bus
and react to events they receive. This is what "event-driven" means in
practice, not just in theory.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """Base class. Every event has a timestamp - when it occurred in
    market time (not necessarily when your code processed it)."""
    timestamp: datetime


@dataclass
class TickEvent(Event):
    """A single price update for a symbol at a point in time.
    This is the only event the DataEngine ever produces."""
    symbol: str
    price: float


@dataclass
class OrderEvent(Event):
    """A strategy wants to buy or sell. This does NOT mean the trade
    has happened yet - it's a request, not a fact."""
    symbol: str
    side: str      # "BUY" or "SELL"
    quantity: int


@dataclass
class FillEvent(Event):
    """An order has actually been executed at some price.
    This is a fact, not a request - the trade has happened."""
    symbol: str
    side: str
    quantity: int
    fill_price: float
