"""Integration tests for ticker sync endpoint."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import create_app
from app.features.auth.dependencies import get_current_user
from app.features.core.database import get_async_session
from app.features.universes.shared.alpaca_assets import AssetInfo

pytestmark = pytest.mark.integration

MOCK_ALPACA_MAP = {
    "AAPL": AssetInfo(
        symbol="AAPL", exchange="NASDAQ", asset_type="equity", tradable=True
    ),
    "MSFT": AssetInfo(
        symbol="MSFT", exchange="NASDAQ", asset_type="equity", tradable=True
    ),
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
async def test_ticker_sync_endpoint_returns_changes(admin_client: AsyncClient):
    """Mock Alpaca → endpoint inserts and returns counts."""
    with patch(
        "app.features.universes.endpoints.ticker_sync.get_alpaca_asset_map",
        return_value=MOCK_ALPACA_MAP,
    ):
        resp = await admin_client.post("/api/v1/tickers/sync")

    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 3
    assert data["updated"] == 0
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_ticker_sync_is_idempotent(admin_client: AsyncClient):
    """Second sync should have zero inserted."""
    with patch(
        "app.features.universes.endpoints.ticker_sync.get_alpaca_asset_map",
        return_value=MOCK_ALPACA_MAP,
    ):
        await admin_client.post("/api/v1/tickers/sync")
        resp = await admin_client.post("/api/v1/tickers/sync")

    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 0
    assert data["updated"] == 3
    assert data["total"] == 3
