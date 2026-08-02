"""
One-off script to verify REDIS_URL actually connects before running
the full live-mode pipeline. Delete this once confirmed working.
"""

import asyncio
import os
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()


async def main():
    redis_url = os.environ["REDIS_URL"]
    client = redis.from_url(redis_url)

    pong = await client.ping()
    print(f"Connected successfully: {pong}")

    await client.set("flowtrade:test_key", "hello")
    value = await client.get("flowtrade:test_key")
    print(f"Set and read back: {value}")

    await client.delete("flowtrade:test_key")
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())