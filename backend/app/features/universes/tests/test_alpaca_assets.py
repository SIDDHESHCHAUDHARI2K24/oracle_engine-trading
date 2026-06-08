"""Tests for the Alpaca asset-list client — all Alpaca APIs are mocked."""

from unittest.mock import MagicMock, patch

import app.features.universes.shared.alpaca_assets as mod
from app.features.universes.shared.alpaca_assets import (
    AssetInfo,
    normalize_symbol,
)


def _clear_cache() -> None:
    mod._cache.clear()
    mod._cache_ts = 0.0


def _make_mock_asset(symbol: str, exchange: str, tradable: bool) -> MagicMock:
    asset = MagicMock()
    asset.symbol = symbol
    asset.exchange = exchange
    asset.tradable = tradable
    return asset


def test_normalize_symbol() -> None:
    assert normalize_symbol("BRK.B") == "BRK-B"
    assert normalize_symbol("brk.b") == "BRK-B"
    assert normalize_symbol("aapl") == "AAPL"
    assert normalize_symbol("  aapl  ") == "AAPL"


def test_get_alpaca_asset_map_returns_dict() -> None:
    _clear_cache()
    mock_assets = [
        _make_mock_asset("AAPL", "NASDAQ", True),
        _make_mock_asset("MSFT", "NASDAQ", True),
        _make_mock_asset("NVDA", "NASDAQ", True),
    ]
    with patch.object(mod, "TradingClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_all_assets.return_value = mock_assets
        mock_client_cls.return_value = mock_client

        result = mod.get_alpaca_asset_map()

    assert isinstance(result, dict)
    assert "AAPL" in result
    assert "MSFT" in result
    assert "NVDA" in result
    assert result["AAPL"] == AssetInfo(
        symbol="AAPL", exchange="NASDAQ", asset_type="equity", tradable=True
    )
    assert result["MSFT"].exchange == "NASDAQ"


def test_get_alpaca_asset_map_filters_tradable() -> None:
    _clear_cache()
    mock_assets = [
        _make_mock_asset("AAPL", "NASDAQ", True),
        _make_mock_asset("FAKE", "NASDAQ", False),
        _make_mock_asset("MSFT", "NASDAQ", True),
        _make_mock_asset("BADD", "NYSE", False),
    ]
    with patch.object(mod, "TradingClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_all_assets.return_value = mock_assets
        mock_client_cls.return_value = mock_client

        result = mod.get_alpaca_asset_map()

    assert "AAPL" in result
    assert "MSFT" in result
    assert "FAKE" not in result
    assert "BADD" not in result
    assert len(result) == 2


def test_get_alpaca_asset_map_caches() -> None:
    _clear_cache()

    mock_assets = [
        _make_mock_asset("AAPL", "NASDAQ", True),
    ]
    with patch.object(mod, "TradingClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_all_assets.return_value = mock_assets
        mock_client_cls.return_value = mock_client

        result1 = mod.get_alpaca_asset_map()

    with patch.object(mod, "TradingClient") as mock_client_cls2:
        mock_client2 = MagicMock()
        mock_client2.get_all_assets.return_value = []
        mock_client_cls2.return_value = mock_client2

        result2 = mod.get_alpaca_asset_map()

    mock_client.get_all_assets.assert_called_once()
    assert result1 is result2
    assert len(result2) == 1
