"""Pydantic v2 schemas for universes API responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TickerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    name: str
    exchange: str | None
    asset_type: str
    active: bool


class UniverseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str | None = None
    public_id: str | None = None
    last_retrain_at: datetime | None = None
    is_system_managed: bool
    created_at: datetime
    ticker_count: int = 0


class UniverseDetail(UniverseSummary):
    tickers: list[TickerSummary] = []


class UniverseListResponse(BaseModel):
    universes: list[UniverseSummary]
    total: int


class UniverseCreate(BaseModel):
    name: str
    display_name: str
    description: str | None = None


class UniverseUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    description: str | None = None


class AddMembersRequest(BaseModel):
    symbols: list[str]


class AddResult(BaseModel):
    added: list[str]
    already_present: list[str]
    invalid: list[str]
