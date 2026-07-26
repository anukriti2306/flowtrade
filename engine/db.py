"""
Database schema and connection setup.

Two tables:
- backtest_runs: one row per time you run the engine, so results from
  different runs (different strategies, date ranges, symbols) don't
  get mixed together.
- fills: every FillEvent that happened during a run, linked back to
  that run via run_id.

Using async SQLAlchemy since the rest of the engine is async - a
blocking DB call inside an async event handler would stall the whole
event loop, defeating the point of using asyncio in the first place.
"""

import os
from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20))
    strategy_name: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[datetime]
    end_date: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(20))
    side: Mapped[str] = mapped_column(String(4))  # "BUY" or "SELL"
    quantity: Mapped[int]
    fill_price: Mapped[float]
    timestamp: Mapped[datetime]


# Connection setup - reads from environment, same pattern as the
# Alpaca keys. DATABASE_URL goes in .env, never hardcoded.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/flowtrade",
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Create tables if they don't exist yet. Safe to call every run -
    won't touch tables that already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)