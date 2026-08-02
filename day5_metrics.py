"""
Day 5: compute and display backtest metrics from a previously
persisted run. Doesn't touch the event pipeline at all - reads
purely from what's already in PostgreSQL.
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from engine.metrics import compute_metrics


async def main():
    run_id = int(input("Enter run_id to analyze (e.g. 4): "))

    metrics = await compute_metrics(run_id)

    print(f"\n--- Backtest Metrics: Run #{metrics.run_id} ---")
    print(f"Total trades:       {metrics.total_trades}")
    print(f"Winning trades:     {metrics.winning_trades}")
    print(f"Losing trades:      {metrics.losing_trades}")
    print(f"Win rate:           {metrics.win_rate:.1f}%")
    print(f"Total P&L:          ₹{metrics.total_pnl:,.2f}")
    print(f"Total return:       {metrics.total_return_pct:.2f}%")
    print(f"Max drawdown:       {metrics.max_drawdown_pct:.2f}%")
    print(f"Avg P&L per trade:  ₹{metrics.avg_pnl_per_trade:,.2f}")


if __name__ == "__main__":
    asyncio.run(main())