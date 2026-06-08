"""Integration tests for JWT auth endpoints.

These tests exercise the actual HTTP layer via httpx.AsyncClient.
The admin user is seeded in the testcontainers database by the conftest.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.features.core.database import get_async_session

ADMIN_EMAIL = "admin@mbilabs.io"
ADMIN_PASSWORD = "change-me-on-first-login"

pytestmark = pytest.mark.integration


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
async def test_login_valid_credentials_returns_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == ADMIN_EMAIL


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "any"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_bearer_token_returns_user(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == ADMIN_EMAIL
    assert resp.json()["is_admin"] is True


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_valid_token_returns_ok(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]
    resp = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
