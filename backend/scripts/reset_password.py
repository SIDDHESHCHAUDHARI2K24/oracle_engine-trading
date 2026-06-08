"""Generate a password-reset token for a user and print it to stdout.

Usage:
    uv run python scripts/reset_password.py admin@mbilabs.io
"""

import asyncio
import hashlib
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mbi_user:mbi_password@localhost:5433/mbi"
)

engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False,
)
sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def reset_password(email: str) -> None:
    token_raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)

    async with sessionmaker() as session:
        result = await session.execute(
            text(
                "UPDATE users SET reset_token_hash = :hash, reset_token_expires_at = :expires "
                "WHERE email = :email AND deleted_at IS NULL"
            ),
            {"hash": token_hash, "expires": expires, "email": email},
        )
        await session.commit()
        if result.rowcount == 0:
            print(f"No active user found with email: {email}", file=sys.stderr)
            sys.exit(1)

    print(token_raw)
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/reset_password.py <email>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(reset_password(sys.argv[1]))
