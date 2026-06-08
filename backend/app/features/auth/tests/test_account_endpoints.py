"""Integration tests for account management endpoints."""

from collections.abc import AsyncGenerator

import pytest
from argon2 import PasswordHasher
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.features.core.database import get_async_session

ADMIN_EMAIL = "admin@mbilabs.io"
ADMIN_PASSWORD = "change-me-on-first-login"

pytestmark = pytest.mark.integration
ph = PasswordHasher()


@pytest.fixture
async def client(database_url: str):
    async_url = database_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    ).replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(async_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    from app.app import create_app

    app = create_app()
    app.dependency_overrides[get_async_session] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    await engine.dispose()


@pytest.mark.asyncio
async def test_change_password_endpoint(client: AsyncClient) -> None:
    # Create a separate test user to avoid corrupting the shared admin account
    test_email = "pw-change-test@example.com"
    test_pw = "original-password-123"

    app_overrides = client._transport.app.dependency_overrides  # type: ignore[attr-defined]
    async with app_overrides[get_async_session]() as ctx:
        async for session in ctx:
            await session.execute(
                text(
                    "INSERT INTO users (email, hashed_password, is_admin, full_name) "
                    "VALUES (:email, :pw, false, :name) "
                    "ON CONFLICT (email) DO UPDATE SET hashed_password = :pw"
                ),
                {"email": test_email, "pw": ph.hash(test_pw), "name": "Test User"},
            )
            await session.commit()

    login = await client.post(
        "/api/v1/auth/login", json={"email": test_email, "password": test_pw}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": test_pw, "new_password": "a-new-password-for-test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Password changed"


@pytest.mark.asyncio
async def test_list_sessions_endpoint(client: AsyncClient) -> None:
    login = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_logout_everywhere_endpoint(client: AsyncClient) -> None:
    login = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]

    resp = await client.post(
        "/api/v1/auth/logout-everywhere",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "ok"
