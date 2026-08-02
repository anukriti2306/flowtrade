"""
Backtest metrics.

Computes performance metrics from fills. The pure P&L/drawdown math
lives in _compute_from_fills(), which takes plain fill-like objects
and returns a BacktestMetrics - no database dependency, so it can be
unit tested directly with fake data. compute_metrics() is the thin
wrapper that fetches real fills from Postgres and calls the pure
function.

Key assumption: this strategy always fully closes a position before
opening a new one (position goes 0 -> 10 -> 0 -> 10 -> 0...), so
fills can be paired up consecutively in timestamp order without
needing a more general trade-matching algorithm.
"""

from dataclasses import dataclass, field
from typing import Protocol
from sqlalchemy import select

from engine.db import async_session, Fill


class FillLike(Protocol):
    """Anything with these three attributes can be scored - a real
    Fill row from the DB, or a plain fake object in a test."""
    side: str
    fill_price: float
    quantity: int


@dataclass
class BacktestMetrics:
    run_id: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_return_pct: float
    max_drawdown_pct: float
    avg_pnl_per_trade: float
    equity_curve: list[float] = field(default_factory=list)


def _compute_from_fills(
    run_id: int, fills: list[FillLike], starting_capital: float = 10000.0
) -> BacktestMetrics:
    """Pure function: fills in, metrics out. No I/O, no database -
    fully testable with plain fake objects."""
    if len(fills) < 2:
        raise ValueError(f"Run {run_id} has fewer than 2 fills - nothing to pair.")

    trade_pnls: list[float] = []
    equity_curve: list[float] = [starting_capital]
    running_capital = starting_capital

    for i in range(0, len(fills) - 1, 2):
        entry = fills[i]
        exit_ = fills[i + 1]

        if entry.side == "BUY":
            pnl = (exit_.fill_price - entry.fill_price) * entry.quantity
        else:
            pnl = (entry.fill_price - exit_.fill_price) * entry.quantity

        trade_pnls.append(pnl)
        running_capital += pnl
        equity_curve.append(running_capital)

    total_pnl = sum(trade_pnls)
    winning_trades = sum(1 for p in trade_pnls if p > 0)
    losing_trades = sum(1 for p in trade_pnls if p <= 0)
    total_trades = len(trade_pnls)

    peak = equity_curve[0]
    max_drawdown_pct = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown_pct = (peak - value) / peak * 100
        if drawdown_pct > max_drawdown_pct:
            max_drawdown_pct = drawdown_pct

    return BacktestMetrics(
        run_id=run_id,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=(winning_trades / total_trades * 100) if total_trades else 0.0,
        total_pnl=total_pnl,
        total_return_pct=(total_pnl / starting_capital) * 100,
        max_drawdown_pct=max_drawdown_pct,
        avg_pnl_per_trade=(total_pnl / total_trades) if total_trades else 0.0,
        equity_curve=equity_curve,
    )


async def compute_metrics(run_id: int, starting_capital: float = 10000.0) -> BacktestMetrics:
    """Fetch real fills for a run from Postgres, then delegate to the
    pure function to do the actual math."""
    async with async_session() as session:
        result = await session.execute(
            select(Fill).where(Fill.run_id == run_id).order_by(Fill.timestamp)
        )
        fills = result.scalars().all()

    return _compute_from_fills(run_id, fills, starting_capital)