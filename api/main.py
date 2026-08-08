"""
FastAPI layer for flowtrade.

Exposes the backtest engine over HTTP, and live paper-trading mode
over a WebSocket. Triggering a backtest returns immediately with a
run_id - the actual backtest runs in a BackgroundTask, since a real
replay can take several seconds and an HTTP client shouldn't have to
hold a connection open waiting for it.

Live mode follows the same event-driven principle used throughout the
engine: WebSocketBroadcaster is just another independent subscriber
to the event bus, alongside Strategy and PersistenceService - none of
them know it exists.

_live_broadcaster is created ONCE at module load and persists across
live runs, so a browser can connect to /ws/live at any time - before,
during, or between live runs - and always be correctly attached once
a run does start. See ws_broadcaster.py for why this matters.
"""
from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.bus import EventBus
from engine.data_engine import HistoricalDataEngine
from engine.live_data_engine import LiveDataEngine
from engine.strategy import MovingAverageCrossStrategy
from engine.execution import ExecutionEngine
from engine.persistence import PersistenceService
from engine.ws_broadcaster import WebSocketBroadcaster
from engine.db import init_db, async_session, BacktestRun, Fill
from engine.metrics import compute_metrics
from sqlalchemy import select
import asyncio
app = FastAPI(title="flowtrade")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://flowtrade.vercel.app",  # update this after Vercel gives you the real URL
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Created once, persists across live runs - see module docstring.
_live_broadcaster = WebSocketBroadcaster()
_live_task: asyncio.Task | None = None


class BacktestRequest(BaseModel):
    symbol: str = "AAPL"
    start: str
    end: str
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
    bus = EventBus()

    strategy = MovingAverageCrossStrategy(bus, short_window=short_window, long_window=long_window)
    execution = ExecutionEngine(bus, slippage_pct=0.001)
    persistence = PersistenceService(bus, run_id=run_id)
    data_engine = HistoricalDataEngine(bus, symbol=symbol, start=start, end=end, replay_delay=0)

    await strategy.register()
    await execution.register()
    await persistence.register()

    bus_task = asyncio.create_task(bus.run())
    await data_engine.run()
    await bus._queue.join()
    bus_task.cancel()


@app.post("/backtest", response_model=BacktestResponse)
async def trigger_backtest(req: BacktestRequest, background_tasks: BackgroundTasks):
    try:
        start = datetime.strptime(req.start, "%Y-%m-%d")
        end = datetime.strptime(req.end, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="start and end must be dates in YYYY-MM-DD format")

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
    async with async_session() as session:
        result = await session.execute(select(BacktestRun).where(BacktestRun.id == run_id))
        run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    try:
        metrics = await compute_metrics(run_id)
        metrics_dict = metrics.__dict__
    except ValueError:
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
@app.get("/live/runs")
async def list_live_runs():
    """All past live sessions, most recent first."""
    async with async_session() as session:
        result = await session.execute(
            select(BacktestRun)
            .where(BacktestRun.strategy_name.like("%-LIVE"))
            .order_by(BacktestRun.created_at.desc())
        )
        runs = result.scalars().all()

    return [
        {"run_id": r.id, "symbol": r.symbol, "created_at": r.created_at.isoformat()}
        for r in runs
    ]


@app.get("/live/runs/{run_id}/fills")
async def get_live_run_fills(run_id: int):
    """Replay a past live session's fills, in order - reconstructs
    the event history from what was actually persisted, since raw
    ticks/orders aren't stored, only completed fills."""
    async with async_session() as session:
        result = await session.execute(
            select(Fill).where(Fill.run_id == run_id).order_by(Fill.timestamp)
        )
        fills = result.scalars().all()

    return [
        {
            "type": "fill",
            "symbol": f.symbol,
            "side": f.side,
            "quantity": f.quantity,
            "fill_price": f.fill_price,
            "timestamp": f.timestamp.isoformat(),
        }
        for f in fills
    ]

async def _run_live(run_id: int, symbol: str):
    bus = EventBus()

    strategy = MovingAverageCrossStrategy(bus, short_window=5, long_window=20)
    execution = ExecutionEngine(bus, slippage_pct=0.001)
    persistence = PersistenceService(bus, run_id=run_id)
    data_engine = LiveDataEngine(bus)

    _live_broadcaster.attach(bus)

    await strategy.register()
    await execution.register()
    await persistence.register()
    await _live_broadcaster.register()

    bus_task = asyncio.create_task(bus.run())
    try:
        await data_engine.run()
    except asyncio.CancelledError:
        pass
    finally:
        bus_task.cancel()


@app.post("/live/start")
async def start_live(background_tasks: BackgroundTasks):
    global _live_task

    async with async_session() as session:
        run = BacktestRun(
            symbol="AAPL",
            strategy_name="MovingAverageCross(5,20)-LIVE",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    _live_task = asyncio.create_task(_run_live(run_id, "AAPL"))
    return {"run_id": run_id, "status": "live"}


@app.post("/live/stop")
async def stop_live():
    global _live_task
    if _live_task and not _live_task.done():
        _live_task.cancel()
    _live_task = None
    return {"status": "stopped"}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    _live_broadcaster.connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _live_broadcaster.disconnect(websocket)


@app.get("/")
async def root():
    return {"status": "flowtrade API running"}