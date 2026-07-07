"""Pydantic v2 schemas for the data_ingestion feature."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import ConfigDict, Field

from app.features.core.base_model import BaseSchema


class OHLCVBarSchema(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    ticker_id: UUID
    bar_date: date
    open: Decimal = Field(max_digits=18, decimal_places=6)
    high: Decimal = Field(max_digits=18, decimal_places=6)
    low: Decimal = Field(max_digits=18, decimal_places=6)
    close: Decimal = Field(max_digits=18, decimal_places=6)
    adjusted_close: Decimal | None = Field(default=None, max_digits=18, decimal_places=6)
    volume: int
    source: str
    ingest_run_id: UUID | None = None
    created_at: datetime


class OHLCVBarResponse(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    ticker_id: UUID
    symbol: str = ""
    bar_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None = None
    volume: int
    source: str


class MacroObservationSchema(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    series_name: str
    observed_date: date
    value: Decimal = Field(max_digits=18, decimal_places=6)
    source: str = "fred"
    is_forward_filled: bool = False
    ingest_run_id: UUID | None = None
    created_at: datetime


class IngestRunSchema(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    triggered_by: str
    triggered_at: datetime
    completed_at: datetime | None = None
    status: str = "running"
    ohlcv_rows_inserted: int = 0
    macro_rows_inserted: int = 0
    failed_tickers: list[str] | None = None
    stale_macro: bool = False
    error_summary: str | None = None


class IngestRunResponse(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    triggered_by: str
    triggered_at: datetime
    completed_at: datetime | None = None
    status: str
    ohlcv_rows_inserted: int
    macro_rows_inserted: int
    failed_tickers: list[str] | None = None
    stale_macro: bool
    error_summary: str | None = None


class IngestionStatusResponse(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    latest_run: IngestRunResponse | None = None
    per_universe_freshness: list[dict] = Field(default_factory=list)


class IngestionTriggerRequest(BaseSchema):
    universe_id: UUID | None = None
    mode: str = "incremental"


class IngestionTriggerResponse(BaseSchema):
    message: str
    run_id: UUID | None = None
    prefect_run_id: UUID | None = None
