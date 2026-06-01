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
    is_system_managed: bool
    created_at: datetime


class UniverseDetail(UniverseSummary):
    tickers: list[TickerSummary] = []


class UniverseListResponse(BaseModel):
    universes: list[UniverseSummary]
    total: int
