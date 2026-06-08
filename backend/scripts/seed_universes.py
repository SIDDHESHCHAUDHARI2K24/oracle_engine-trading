"""Seed system-managed universes (S&P 500, Russell 1000, Russell 2000).

Idempotent — re-running reconciles memberships (adds new constituents,
marks departed ones as removed, preserving history).
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def seed_universes():
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from app.features.core.config import settings
    from app.features.universes import service as universes_service
    from app.features.universes import repository as universes_repo
    from app.features.universes.shared.constituents.adapters.sp500 import SP500Source
    from app.features.universes.shared.constituents.adapters.russell1000 import (
        Russell1000Source,
    )
    from app.features.universes.shared.constituents.adapters.russell2000 import (
        Russell2000Source,
    )
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    url = settings.database_url
    if "postgresql://" in url and "postgresql+asyncpg://" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(url)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    indices = [
        ("sp500", "S&P 500", SP500Source()),
        ("russell1000", "Russell 1000", Russell1000Source()),
        ("russell2000", "Russell 2000", Russell2000Source()),
    ]

    async with session_factory() as db:
        for slug, display_name, source in indices:
            logger.info(f"Processing {display_name}...")
            try:
                universe = await universes_repo.get_universe_by_name(db, slug)
                if universe is None:
                    try:
                        universe = await universes_service.create_universe(
                            db, name=slug, display_name=display_name
                        )
                        universe.is_system_managed = True
                        await db.flush()
                    except ValueError as e:
                        logger.warning(f"  Universe create failed: {e}")
                        continue

                symbols = await source.fetch_constituents()
                logger.info(f"  Fetched {len(symbols)} constituents")

                result = await universes_service.add_members(db, universe.id, symbols)
                logger.info(
                    f"  Added: {len(result.added)}, Already present: {len(result.already_present)}, Invalid: {len(result.invalid)}"
                )

                if result.invalid:
                    logger.warning(f"  Invalid symbols: {result.invalid[:10]}...")

            except Exception as e:
                logger.error(f"  Failed to seed {display_name}: {e}")

    await engine.dispose()
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed_universes())
