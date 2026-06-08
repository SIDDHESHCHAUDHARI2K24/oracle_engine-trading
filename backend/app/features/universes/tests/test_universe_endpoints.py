"""Integration tests for universe CRUD endpoints.

Uses httpx.AsyncClient + ASGITransport against the full FastAPI app.
Requires an admin user seeded in the test database.
"""

import os

import pytest
from argon2 import PasswordHasher
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.features.auth.service import issue_access_token

pytestmark = pytest.mark.integration
ph = PasswordHasher()

ADMIN_EMAIL = "admin@mbilabs.io"
ADMIN_PASSWORD = "change-me-on-first-login"


async def _seed_admin(database_url: str) -> str:
    """Seed an admin user in the DB and return a JWT access token."""
    async_url = database_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    ).replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, echo=False)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    hashed = ph.hash(ADMIN_PASSWORD)
    async with sessionmaker() as session:
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": ADMIN_EMAIL},
        )
        existing = result.scalar_one_or_none()

        if existing:
            user_id = existing
        else:
            result = await session.execute(
                text(
                    "INSERT INTO users (email, hashed_password, is_admin) "
                    "VALUES (:email, :hashed, TRUE) RETURNING id"
                ),
                {"email": ADMIN_EMAIL, "hashed": hashed},
            )
            user_id = result.scalar_one()

        await session.commit()

    token = issue_access_token(user_id)
    await engine.dispose()
    return token


@pytest.fixture
async def admin_token(database_url: str) -> str:
    return await _seed_admin(database_url)


@pytest.fixture
async def client(admin_token: str, database_url: str):
    plain_url = database_url.replace("postgresql+psycopg2://", "postgresql://")
    os.environ["DATABASE_URL"] = plain_url

    import importlib

    import app.features.core.config as config_mod
    import app.features.core.database as db_mod

    importlib.reload(config_mod)
    importlib.reload(db_mod)

    from app.app import create_app

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_universe_returns_201(
    admin_token: str, client: AsyncClient
) -> None:
    resp = await client.post(
        "/api/v1/universes",
        json={
            "name": "test-universe",
            "display_name": "Test Universe",
            "description": "Created via test",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-universe"
    assert data["display_name"] == "Test Universe"
    assert data["description"] == "Created via test"
    assert data["public_id"] is not None
    assert data["public_id"].startswith("uni_")


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(
    admin_token: str, client: AsyncClient
) -> None:
    payload = {"name": "dup-api", "display_name": "Dup API"}
    r1 = await client.post(
        "/api/v1/universes",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/universes",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"]["error_code"] == "DUPLICATE_UNIVERSE_NAME"


@pytest.mark.asyncio
async def test_update_universe_returns_200(
    admin_token: str, client: AsyncClient
) -> None:
    create_resp = await client.post(
        "/api/v1/universes",
        json={"name": "update-test", "display_name": "Update Test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    universe_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/universes/{universe_id}",
        json={"name": "renamed", "display_name": "Renamed", "description": "New desc"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "renamed"
    assert data["display_name"] == "Renamed"
    assert data["description"] == "New desc"


@pytest.mark.asyncio
async def test_delete_universe_returns_200(
    admin_token: str, client: AsyncClient
) -> None:
    create_resp = await client.post(
        "/api/v1/universes",
        json={"name": "delete-test", "display_name": "Delete Test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    universe_id = create_resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/universes/{universe_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"detail": "ok"}

    get_resp = await client.get(
        f"/api/v1/universes/{universe_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_system_managed_returns_403(
    admin_token: str, client: AsyncClient, database_url: str
) -> None:
    async_url = database_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    ).replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, echo=False)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO universes (name, display_name, description, is_system_managed, public_id) "
                "VALUES ('sys-api', 'System API', 'sys', TRUE, 'uni_sysapi')"
            )
        )
        await session.commit()

        result = await session.execute(
            text("SELECT id FROM universes WHERE name = 'sys-api'")
        )
        sys_id = str(result.scalar_one())

    resp = await client.delete(
        f"/api/v1/universes/{sys_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error_code"] == "SYSTEM_MANAGED_UNIVERSE"

    await engine.dispose()


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/universes",
        json={"name": "no-auth", "display_name": "No Auth"},
    )
    assert resp.status_code == 401
