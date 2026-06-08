"""Tests for constituent source adapters against saved fixtures."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_sp500_parse():
    """SP500 adapter parses fixture correctly."""
    html_content = (FIXTURES_DIR / "sp500_sample.html").read_text()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.text = html_content
        mock_get.return_value.raise_for_status = lambda: None
        from app.features.universes.shared.constituents.adapters.sp500 import SP500Source
        source = SP500Source()
        symbols = await source.fetch_constituents()
    assert len(symbols) > 0
    assert all(s == s.upper() for s in symbols)
    assert "." not in "".join(symbols)


@pytest.mark.asyncio
async def test_russell1000_parse():
    """Russell 1000 adapter parses fixture correctly."""
    csv_content = (FIXTURES_DIR / "iwb_holdings_sample.csv").read_text()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.text = csv_content
        mock_get.return_value.raise_for_status = lambda: None
        from app.features.universes.shared.constituents.adapters.russell1000 import Russell1000Source
        source = Russell1000Source()
        symbols = await source.fetch_constituents()
    assert len(symbols) > 0
    assert all(s == s.upper() for s in symbols)


@pytest.mark.asyncio
async def test_russell2000_parse():
    """Russell 2000 adapter parses fixture correctly."""
    csv_content = (FIXTURES_DIR / "iwb_holdings_sample.csv").read_text()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.text = csv_content
        mock_get.return_value.raise_for_status = lambda: None
        from app.features.universes.shared.constituents.adapters.russell2000 import Russell2000Source
        source = Russell2000Source()
        symbols = await source.fetch_constituents()
    assert len(symbols) > 0
    assert all(s == s.upper() for s in symbols)


def test_normalize_constituent_symbol():
    """Symbol normalization: dots to dashes, uppercase."""
    from app.features.universes.shared.constituents.base import normalize_constituent_symbol
    assert normalize_constituent_symbol("BRK.B") == "BRK-B"
    assert normalize_constituent_symbol(" aapl ") == "AAPL"
    assert normalize_constituent_symbol("BF.B") == "BF-B"
