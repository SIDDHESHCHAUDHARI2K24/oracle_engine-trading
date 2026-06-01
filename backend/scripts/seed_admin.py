"""Seed the admin user defined in environment variables.

Idempotent — safe to run repeatedly.  The password is argon2-hashed
before storage and never logged.

Usage:
    uv run python scripts/seed_admin.py
"""

import asyncio
import os

from argon2 import PasswordHasher
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@mbilabs.io")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-on-first-login")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mbi_user:mbi_password@localhost:5433/mbi")

ph = PasswordHasher()

engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
)
sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed_admin() -> None:
    hashed = ph.hash(ADMIN_PASSWORD)
    async with sessionmaker() as session:
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": ADMIN_EMAIL},
        )
        existing = result.scalar_one_or_none()

        if existing:
            await session.execute(
                text(
                    "UPDATE users SET hashed_password = :hashed, is_admin = TRUE "
                    "WHERE email = :email"
                ),
                {"hashed": hashed, "email": ADMIN_EMAIL},
            )
            await session.commit()
            print(f"Admin user '{ADMIN_EMAIL}' updated.")
        else:
            await session.execute(
                text(
                    "INSERT INTO users (email, hashed_password, is_admin) "
                    "VALUES (:email, :hashed, TRUE)"
                ),
                {"email": ADMIN_EMAIL, "hashed": hashed},
            )
            await session.commit()
            print(f"Admin user '{ADMIN_EMAIL}' created.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_admin())
