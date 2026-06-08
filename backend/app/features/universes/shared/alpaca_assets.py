"""Alpaca Markets asset-list client with caching and retry."""

import logging
import time
from dataclasses import dataclass

from alpaca.trading.client import TradingClient
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from app.features.core.config import settings

logger = logging.getLogger(__name__)

ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"

_cache: dict[str, "AssetInfo"] = {}
_cache_ts: float = 0.0
CACHE_TTL_SECONDS: int = 3600


@dataclass(frozen=True)
class AssetInfo:
    symbol: str
    exchange: str
    asset_type: str
    tradable: bool


def normalize_symbol(raw: str) -> str:
    return raw.strip().upper().replace(".", "-")


@retry(
    wait=wait_exponential(min=2, max=30),
    stop=stop_after_attempt(3),
)
def _fetch_alpaca_assets() -> dict[str, AssetInfo]:
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        logger.warning("Alpaca API keys not configured — returning empty asset map")
        return {}

    from alpaca.trading.enums import AssetClass, AssetStatus
    from alpaca.trading.requests import GetAssetsRequest

    client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        url_override=ALPACA_PAPER_URL,
    )
    request = GetAssetsRequest(
        status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY
    )
    raw = client.get_all_assets(request)
    result: dict[str, AssetInfo] = {}
    for asset in raw:
        if isinstance(asset, str):
            continue
        if not asset.tradable:
            continue
        info = AssetInfo(
            symbol=asset.symbol,
            exchange=asset.exchange or "",
            asset_type="etf" if _is_likely_etf(asset) else "equity",
            tradable=asset.tradable,
        )
        result[asset.symbol.upper()] = info
    return result


def _is_likely_etf(asset: object) -> bool:
    exchange = getattr(asset, "exchange", "") or ""
    return exchange.upper() in {"ARCA", "BATS", "NYSEARCA"}


def get_alpaca_asset_map() -> dict[str, AssetInfo]:
    global _cache, _cache_ts

    now = time.monotonic()
    if _cache and (now - _cache_ts) < CACHE_TTL_SECONDS:
        return _cache

    logger.info("Fetching fresh Alpaca asset list")
    _cache = _fetch_alpaca_assets()
    _cache_ts = time.monotonic()
    return _cache
