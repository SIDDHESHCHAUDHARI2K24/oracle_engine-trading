"""Feature engineering Pydantic schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FeatureMatrixRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker_id: UUID
    bar_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    returns_1d: Optional[Decimal] = None
    returns_5d: Optional[Decimal] = None
    returns_10d: Optional[Decimal] = None
    returns_20d: Optional[Decimal] = None
    rsi_14: Optional[Decimal] = None
    macd: Optional[Decimal] = None
    macd_signal: Optional[Decimal] = None
    macd_hist: Optional[Decimal] = None
    bb_upper: Optional[Decimal] = None
    bb_middle: Optional[Decimal] = None
    bb_lower: Optional[Decimal] = None
    bb_width: Optional[Decimal] = None
    atr_14: Optional[Decimal] = None
    volatility_20d: Optional[Decimal] = None
    volume_z_score: Optional[Decimal] = None
    sma_50: Optional[Decimal] = None
    sma_200: Optional[Decimal] = None
    price_to_sma50: Optional[Decimal] = None
    price_to_sma200: Optional[Decimal] = None

    fed_funds_rate: Optional[Decimal] = None
    cpi: Optional[Decimal] = None
    unemployment: Optional[Decimal] = None
    gdp: Optional[Decimal] = None
    yield_spread_10y_2y: Optional[Decimal] = None
    vix: Optional[Decimal] = None
    high_yield_spread: Optional[Decimal] = None

    target_t1: Optional[Decimal] = None
    target_t5: Optional[Decimal] = None
    target_t10: Optional[Decimal] = None
    target_t15: Optional[Decimal] = None

    feature_schema_version: str
    computed_at: datetime


class NormalizationStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker_id: UUID
    bar_date: date
    feature_name: str
    rolling_mean: Decimal
    rolling_std: Decimal


class FeatureInspectResponse(BaseModel):
    ticker: str
    date: date
    features: dict[str, Optional[float]]
    targets: dict[str, Optional[float]]
    stats: list[dict]


class TriggerRequest(BaseModel):
    mode: str = "incremental"
    ticker_symbol: Optional[str] = None
    universe_name: Optional[str] = None


class TriggerResponse(BaseModel):
    status: str
    features_upserted: int
    stats_upserted: int
    errors: list[str]
