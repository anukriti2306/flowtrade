"""
The DataEngine - Alpaca version.

Same job as before: read historical price data, replay it as a
stream of TickEvents, in chronological order. The only thing that's
changed from the yfinance version is where the data comes from - the
Strategy and ExecutionEngine don't know or care about this swap,
which is exactly the point of the event-driven design.

Timestamps are kept in UTC throughout the entire event pipeline -
ticks, orders, fills, and database storage all stay UTC. Converting
to local time anywhere inside the pipeline causes timezone-aware and
timezone-naive datetimes to clash later (e.g. against a naive
TIMESTAMP column in Postgres). Conversion to local time, if wanted,
should only happen at the very last step - when printing to the
console for a human to read - not threaded through the internals.
"""

import asyncio
import os
from datetime import datetime

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from engine.bus import EventBus
from engine.events import TickEvent


class HistoricalDataEngine:
    def __init__(self, bus: EventBus, symbol: str, start: datetime, end: datetime,
                 replay_delay: float = 0.1):
        """
        symbol: e.g. 'AAPL', 'TSLA' - US equities, since Alpaca's free
                tier covers US stocks, not NSE/Indian stocks
        start/end: datetime objects for the historical range
        replay_delay: seconds between ticks - 0 for a fast run
        """
        self.bus = bus
        self.symbol = symbol
        self.start = start
        self.end = end
        self.replay_delay = replay_delay

        api_key = os.environ["APCA_API_KEY_ID"]
        secret_key = os.environ["APCA_API_SECRET_KEY"]
        self.client = StockHistoricalDataClient(api_key, secret_key)

    def _fetch(self):
        """Blocking network call - fetches once, upfront, before any
        events start flowing."""
        request = StockBarsRequest(
            symbol_or_symbols=[self.symbol],
            timeframe=TimeFrame.Day,
            start=self.start,
            end=self.end,
        )
        bars = self.client.get_stock_bars(request)
        df = bars.df

        if df.empty:
            raise ValueError(
                f"No data returned for {self.symbol} between {self.start} "
                f"and {self.end}. Check the symbol and date range."
            )
        return df

    async def run(self):
        df = self._fetch()
        print(f"Loaded {len(df)} bars for {self.symbol}")

        # df has a MultiIndex of (symbol, timestamp) - iterate rows in order
        for (symbol, timestamp), row in df.iterrows():
            tick = TickEvent(
                # Stays UTC - no local timezone conversion here.
                timestamp=timestamp.to_pydatetime().replace(tzinfo=None),
                symbol=symbol,
                price=float(row["close"]),
            )
            await self.bus.publish(tick)
            if self.replay_delay > 0:
                await asyncio.sleep(self.replay_delay)

        print("Historical replay complete.")