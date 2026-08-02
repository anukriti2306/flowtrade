"""
FastAPI layer for flowtrade.

Exposes the backtest engine over HTTP. Triggering a backtest returns
immediately with a run_id - the actual backtest runs in a
BackgroundTask, since a real replay can take several seconds and an
HTTP client shouldn't have to hold a connection open waiting for it.

This mirrors the same pattern discussed for the notification system
design: don't make the caller wait on slow work, hand back an ID they
can poll instead.
"""

from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from engine.bus import EventBus
from engine.data_engine import HistoricalDataEngine
from engine.strategy import MovingAverageCrossStrategy
from engine.execution import ExecutionEngine
from engine.persistence import PersistenceService
from engine.db import init_db, async_session, BacktestRun
from engine.metrics import compute_metrics
from sqlalchemy import select


app = FastAPI(title="flowtrade")


class BacktestRequest(BaseModel):
    symbol: str = "AAPL"
    start: str  # "YYYY-MM-DD"
    end: str    # "YYYY-MM-DD"
    short_window: int = 5
    long_window: int = 20


class BacktestResponse(BaseModel):
    run_id: int
    status: str


@app.on_event("startup")
async def startup():
    await init_db()


async def _run_backtest(run_id: int, symbol: str, start: datetime, end: datetime,
                         short_window: int, long_window: int):
    """The actual backtest pipeline - identical to day4_persistence.py's
    main(), just parameterized and running as a background task instead
    of a standalone script. Nothing about the engine itself changes -
    this is the same Strategy/ExecutionEngine/DataEngine/PersistenceService
    wired together the same way."""
    bus = EventBus()

    strategy = MovingAverageCrossStrategy(bus, short_window=short_window, long_window=long_window)
    execution = ExecutionEngine(bus, slippage_pct=0.001)
    persistence = PersistenceService(bus, run_id=run_id)
    data_engine = HistoricalDataEngine(bus, symbol=symbol, start=start, end=end, replay_delay=0)

    await strategy.register()
    await execution.register()
    await persistence.register()

    import asyncio
    bus_task = asyncio.create_task(bus.run())
    await data_engine.run()
    await bus._queue.join()
    bus_task.cancel()


@app.post("/backtest", response_model=BacktestResponse)
@app.post("/backtest", response_model=BacktestResponse)
async def trigger_backtest(req: BacktestRequest, background_tasks: BackgroundTasks):
    try:
        start = datetime.strptime(req.start, "%Y-%m-%d")
        end = datetime.strptime(req.end, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="start and end must be dates in YYYY-MM-DD format",
        )

    async with async_session() as session:
        run = BacktestRun(
            symbol=req.symbol,
            strategy_name=f"MovingAverageCross({req.short_window},{req.long_window})",
            start_date=start,
            end_date=end,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    background_tasks.add_task(
        _run_backtest, run_id, req.symbol, start, end, req.short_window, req.long_window
    )

    return BacktestResponse(run_id=run_id, status="running")
@app.get("/backtest/{run_id}")
async def get_backtest(run_id: int):
    """Fetch the run's metadata and, if it has fills yet, its computed
    metrics. If the backtest is still running in the background, fills
    may not exist yet - that's a valid, expected state, not an error."""
    async with async_session() as session:
        result = await session.execute(select(BacktestRun).where(BacktestRun.id == run_id))
        run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    try:
        metrics = await compute_metrics(run_id)
        metrics_dict = metrics.__dict__
    except ValueError:
        # Fewer than 2 fills - either still running, or no trades happened
        metrics_dict = None

    return {
        "run_id": run.id,
        "symbol": run.symbol,
        "strategy_name": run.strategy_name,
        "start_date": run.start_date,
        "end_date": run.end_date,
        "created_at": run.created_at,
        "metrics": metrics_dict,
    }

@app.get("/backtest/{run_id}/equity-curve")
async def get_equity_curve(run_id: int):
    """Return the equity curve as a simple list of points for
    charting - capital value after each round-trip trade."""
    try:
        metrics = await compute_metrics(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "run_id": run_id,
        "points": [
            {"trade_number": i, "capital": value}
            for i, value in enumerate(metrics.equity_curve)
        ],
    }
@app.get("/")
async def root():
    return {"status": "flowtrade API running"}