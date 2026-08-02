"""
Unit tests for the pure P&L/drawdown math in engine/metrics.py.
No database, no network - these run in milliseconds.
"""

import pytest
from dataclasses import dataclass

from engine.metrics import _compute_from_fills


@dataclass
class FakeFill:
    """Minimal stand-in for a real Fill row - only needs the three
    attributes _compute_from_fills actually reads."""
    side: str
    fill_price: float
    quantity: int


def test_single_winning_trade():
    """Buy low, sell high - should show a profit and a 100% win rate."""
    fills = [
        FakeFill(side="BUY", fill_price=100.0, quantity=10),
        FakeFill(side="SELL", fill_price=110.0, quantity=10),
    ]
    metrics = _compute_from_fills(run_id=1, fills=fills, starting_capital=10000.0)

    assert metrics.total_trades == 1
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 0
    assert metrics.win_rate == 100.0
    assert metrics.total_pnl == pytest.approx(100.0)  # (110-100) * 10


def test_single_losing_trade():
    """Buy high, sell low - should show a loss and 0% win rate."""
    fills = [
        FakeFill(side="BUY", fill_price=110.0, quantity=10),
        FakeFill(side="SELL", fill_price=100.0, quantity=10),
    ]
    metrics = _compute_from_fills(run_id=1, fills=fills, starting_capital=10000.0)

    assert metrics.winning_trades == 0
    assert metrics.losing_trades == 1
    assert metrics.win_rate == 0.0
    assert metrics.total_pnl == pytest.approx(-100.0)


def test_short_trade_profits_on_price_drop():
    """SELL first (short), then BUY back lower - this should be a
    winning trade, since shorts profit when price falls. This is the
    one most likely to have a sign error if the pnl formula is wrong."""
    fills = [
        FakeFill(side="SELL", fill_price=110.0, quantity=10),
        FakeFill(side="BUY", fill_price=100.0, quantity=10),
    ]
    metrics = _compute_from_fills(run_id=1, fills=fills, starting_capital=10000.0)

    assert metrics.winning_trades == 1
    assert metrics.total_pnl == pytest.approx(100.0)  # (110-100) * 10, short profit


def test_equity_curve_starts_at_starting_capital():
    fills = [
        FakeFill(side="BUY", fill_price=100.0, quantity=10),
        FakeFill(side="SELL", fill_price=110.0, quantity=10),
    ]
    metrics = _compute_from_fills(run_id=1, fills=fills, starting_capital=5000.0)

    assert metrics.equity_curve[0] == 5000.0
    assert metrics.equity_curve[-1] == pytest.approx(5100.0)


def test_max_drawdown_detects_peak_to_trough_drop():
    """Three trades: win big, then lose, then partially recover.
    Max drawdown should be measured from the peak after trade 1,
    not from the starting capital."""
    fills = [
        FakeFill(side="BUY", fill_price=100.0, quantity=10),
        FakeFill(side="SELL", fill_price=200.0, quantity=10),  # +1000, capital -> 11000 (peak)
        FakeFill(side="BUY", fill_price=100.0, quantity=10),
        FakeFill(side="SELL", fill_price=50.0, quantity=10),   # -500, capital -> 10500
        FakeFill(side="BUY", fill_price=100.0, quantity=10),
        FakeFill(side="SELL", fill_price=80.0, quantity=10),   # -200, capital -> 10300
    ]
    metrics = _compute_from_fills(run_id=1, fills=fills, starting_capital=10000.0)

    # Peak was 11000, worst point after that was 10300
    # drawdown = (11000 - 10300) / 11000 * 100 ≈ 6.36%
    assert metrics.max_drawdown_pct == pytest.approx(6.3636, rel=1e-3)


def test_raises_on_insufficient_fills():
    """A single unmatched fill (e.g. a position still open) can't be
    paired into a trade - should raise, not silently return garbage."""
    fills = [FakeFill(side="BUY", fill_price=100.0, quantity=10)]

    with pytest.raises(ValueError):
        _compute_from_fills(run_id=1, fills=fills)


def test_odd_number_of_fills_ignores_trailing_unmatched_fill():
    """If there's an odd number of fills (an open position at the end
    of the data), the trailing unmatched fill should be ignored, not
    crash or get paired incorrectly with nothing."""
    fills = [
        FakeFill(side="BUY", fill_price=100.0, quantity=10),
        FakeFill(side="SELL", fill_price=110.0, quantity=10),
        FakeFill(side="BUY", fill_price=105.0, quantity=10),  # unmatched, position still open
    ]
    metrics = _compute_from_fills(run_id=1, fills=fills, starting_capital=10000.0)

    assert metrics.total_trades == 1  # only the completed pair counts