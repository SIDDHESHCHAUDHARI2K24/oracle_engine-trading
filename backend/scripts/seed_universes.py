"""Seed the S&P 500 system-managed universe with 3 representative tickers.

Idempotent — safe to run repeatedly. Uses raw SQL with ON CONFLICT
so re-running won't duplicate rows.

Usage:
    uv run python scripts/seed_universes.py
"""

import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mbi_user:mbi_password@localhost:5433/mbi"
)


UNIVERSES = [
    {
        "name": "sp500",
        "display_name": "S&P 500",
        "is_system_managed": True,
    },
]

TICKERS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "asset_type": "equity"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ", "asset_type": "equity"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ", "asset_type": "equity"},
]

MEMBERSHIPS = [
    ("sp500", "AAPL"),
    ("sp500", "MSFT"),
    ("sp500", "NVDA"),
]


async def upsert_universe(session: AsyncSession, u: dict) -> str:
    result = await session.execute(
        text("SELECT id FROM universes WHERE name = :name AND deleted_at IS NULL"),
        {"name": u["name"]},
    )
    row = result.scalar_one_or_none()
    if row:
        await session.execute(
            text(
                "UPDATE universes SET display_name = :display, is_system_managed = :sm "
                "WHERE id = :id"
            ),
            {"display": u["display_name"], "sm": u["is_system_managed"], "id": row},
        )
        return str(row)
    result = await session.execute(
        text(
            "INSERT INTO universes (name, display_name, is_system_managed) "
            "VALUES (:name, :display, :sm) RETURNING id"
        ),
        {"name": u["name"], "display": u["display_name"], "sm": u["is_system_managed"]},
    )
    return str(result.scalar_one())


async def upsert_ticker(session: AsyncSession, t: dict) -> str:
    result = await session.execute(
        text("SELECT id FROM tickers WHERE symbol = :symbol"),
        {"symbol": t["symbol"]},
    )
    row = result.scalar_one_or_none()
    if row:
        await session.execute(
            text(
                "UPDATE tickers SET name = :name, exchange = :exch, "
                "asset_type = :atype, active = TRUE WHERE id = :id"
            ),
            {"name": t["name"], "exch": t["exchange"], "atype": t["asset_type"], "id": row},
        )
        return str(row)
    result = await session.execute(
        text(
            "INSERT INTO tickers (symbol, name, exchange, asset_type) "
            "VALUES (:symbol, :name, :exch, :atype) RETURNING id"
        ),
        {"symbol": t["symbol"], "name": t["name"], "exch": t["exchange"], "atype": t["asset_type"]},
    )
    return str(result.scalar_one())


async def upsert_membership(
    session: AsyncSession, universe_id: str, ticker_id: str
) -> None:
    result = await session.execute(
        text(
            "SELECT id FROM universe_memberships "
            "WHERE universe_id = :uid AND ticker_id = :tid AND removed_at IS NULL"
        ),
        {"uid": universe_id, "tid": ticker_id},
    )
    if result.scalar_one_or_none() is not None:
        return
    await session.execute(
        text(
            "INSERT INTO universe_memberships (universe_id, ticker_id, added_at) "
            "VALUES (:uid, :tid, :ts)"
        ),
        {"uid": universe_id, "tid": ticker_id, "ts": datetime.now(timezone.utc)},
    )


async def seed() -> None:
    engine = create_async_engine(
        DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False,
    )
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sessionmaker() as session:
        universe_ids: dict[str, str] = {}
        for u in UNIVERSES:
            uid = await upsert_universe(session, u)
            universe_ids[u["name"]] = uid
            print(f"Universe '{u['name']}' upserted ({uid})")

        ticker_ids: dict[str, str] = {}
        for t in TICKERS:
            tid = await upsert_ticker(session, t)
            ticker_ids[t["symbol"]] = tid
            print(f"Ticker '{t['symbol']}' upserted ({tid})")

        for universe_name, ticker_symbol in MEMBERSHIPS:
            await upsert_membership(
                session, universe_ids[universe_name], ticker_ids[ticker_symbol]
            )
            print(f"Membership {universe_name} <- {ticker_symbol}")

        await session.commit()

    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
