"""Integration tests for JWT auth endpoints.

These tests exercise the actual HTTP layer via httpx.AsyncClient using the
seeded admin user (admin@mbilabs.io / change-me-on-first-login).

Pre-conditions:
  - DATABASE_URL and JWT_SECRET env vars are set.
  - Admin user is seeded (run: uv run python scripts/seed_admin.py).
  - In CI these are guaranteed by the workflow before pytest runs.

NOTE: These tests require a running app stack (DB + server). Use
`make test-integration` or run with `pytest -m integration`.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.app import create_app

ADMIN_EMAIL = "admin@mbilabs.io"
ADMIN_PASSWORD = "change-me-on-first-login"

pytestmark = pytest.mark.integration


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_login_valid_credentials_returns_token(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == ADMIN_EMAIL


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "any"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_bearer_token_returns_user(client: AsyncClient) -> None:
    login = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == ADMIN_EMAIL
    assert resp.json()["is_admin"] is True


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_valid_token_returns_ok(client: AsyncClient) -> None:
    login = await client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]
    resp = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
