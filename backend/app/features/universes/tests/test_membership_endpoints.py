"""Integration tests for membership and CSV import endpoints.

Mock Alpaca in ALL tests — never hit live API.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.app import create_app
from app.features.auth.dependencies import get_current_user
from app.features.core.database import get_async_session
from app.features.universes.models import Universe, UniverseMembership
from app.features.universes.shared.alpaca_assets import AssetInfo

pytestmark = pytest.mark.integration

MOCK_ALPACA_MAP = {
    "AAPL": AssetInfo(symbol="AAPL", exchange="NASDAQ", asset_type="equity", tradable=True),
    "MSFT": AssetInfo(symbol="MSFT", exchange="NASDAQ", asset_type="equity", tradable=True),
    "NVDA": AssetInfo(symbol="NVDA", exchange="NASDAQ", asset_type="equity", tradable=True),
    "SPY": AssetInfo(symbol="SPY", exchange="ARCA", asset_type="etf", tradable=True),
}


@dataclass
class MockUser:
    email: str = "admin@test.local"
    is_admin: bool = True


async def _mock_get_current_user():
    return MockUser()


@pytest.fixture
async def admin_client(db_session: AsyncSession):
    app = create_app()

    async def _override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_current_user] = _mock_get_current_user
    app.dependency_overrides[get_async_session] = _override_get_async_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_members_returns_breakdown(admin_client: AsyncClient, db_session: AsyncSession):
    universe = Universe(
        name="endpoint-test", display_name="Endpoint Test", public_id="uni_ep01"
    )
    db_session.add(universe)
    await db_session.flush()

    with patch(
        "app.features.universes.service.get_alpaca_asset_map",
        return_value=MOCK_ALPACA_MAP,
    ):
        resp = await admin_client.post(
            f"/api/v1/universes/{universe.id}/membership",
            json={"symbols": ["AAPL", "FAKE", "MSFT"]},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert set(data["added"]) == {"AAPL", "MSFT"}
    assert data["invalid"] == ["FAKE"]
    assert len(data["already_present"]) == 0


@pytest.mark.asyncio
async def test_remove_member_returns_200(admin_client: AsyncClient, db_session: AsyncSession):
    universe = Universe(
        name="remove-test", display_name="Remove Test", public_id="uni_rm01"
    )
    db_session.add(universe)
    await db_session.flush()

    with patch(
        "app.features.universes.service.get_alpaca_asset_map",
        return_value=MOCK_ALPACA_MAP,
    ):
        add_resp = await admin_client.post(
            f"/api/v1/universes/{universe.id}/membership",
            json={"symbols": ["AAPL"]},
        )
        assert add_resp.status_code == 201

    result = await db_session.execute(
        select(UniverseMembership).where(
            UniverseMembership.universe_id == universe.id,
            UniverseMembership.removed_at.is_(None),
        )
    )
    membership = result.scalar_one()
    ticker_id = membership.ticker_id

    resp = await admin_client.delete(
        f"/api/v1/universes/{universe.id}/membership/{ticker_id}",
    )
    assert resp.status_code == 200
    assert resp.json() == {"detail": "ok"}

    await db_session.refresh(membership)
    assert membership.removed_at is not None


@pytest.mark.asyncio
async def test_csv_import_adds_tickers(admin_client: AsyncClient, db_session: AsyncSession):
    universe = Universe(
        name="csv-test", display_name="CSV Test", public_id="uni_csv01"
    )
    db_session.add(universe)
    await db_session.flush()

    csv_content = "AAPL\nMSFT\nNVDA\n"
    files = {"file": ("symbols.csv", csv_content.encode("utf-8"), "text/csv")}

    with patch(
        "app.features.universes.service.get_alpaca_asset_map",
        return_value=MOCK_ALPACA_MAP,
    ):
        resp = await admin_client.post(
            f"/api/v1/universes/{universe.id}/membership/import",
            files=files,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert set(data["added"]) == {"AAPL", "MSFT", "NVDA"}
    assert len(data["invalid"]) == 0
    assert len(data["already_present"]) == 0
    assert data["parse_errors"] == []

    result = await db_session.execute(
        select(UniverseMembership).where(
            UniverseMembership.universe_id == universe.id,
            UniverseMembership.removed_at.is_(None),
        )
    )
    memberships = result.scalars().all()
    assert len(memberships) == 3
