"""
Simulates a live market feed by publishing prices to a Redis channel.

This is a deliberately SEPARATE process from the main flowtrade app -
in a real system, a live price feed comes from an external exchange,
not from inside your own trading engine. Running this as its own
script honestly reflects that: flowtrade only ever SUBSCRIBES to
prices, exactly as it would to a real broker's live feed.

Run this in one terminal, then run live_data_engine.py (or the day6
live script) in a separate terminal to watch flowtrade consume it.
"""

import asyncio
import json
import os
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

CHANNEL = "flowtrade:live_ticks"


async def main():
    redis_url = os.environ["REDIS_URL"]
    client = redis.from_url(redis_url)

    symbol = "AAPL"
    price = 200.0

    print(f"Publishing simulated live ticks for {symbol} to '{CHANNEL}'. Ctrl+C to stop.")

    try:
        while True:
            # Random walk, just to produce some movement to react to
            price += random.uniform(-1.5, 1.5)
            tick = {
                "symbol": symbol,
                "price": round(price, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await client.publish(CHANNEL, json.dumps(tick))
            print(f"Published: {tick}")
            await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopped publishing.")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())