import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ConvictionTicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inference_date: date
    ticker_id: uuid.UUID
    universe_id: uuid.UUID
    horizon: str
    direction: str
    predicted_return: float
    conviction_score: float
    conformal_lower: float
    conformal_upper: float
    backtest_passes: int
    backtest_pass_strategies: list[str]
    status: str
    resolution_date: date
    actual_return: float | None = None
    outcome: str | None = None
    user_notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TicketListResponse(BaseModel):
    tickets: list[ConvictionTicketResponse]
    total: int


class LifecycleRequest(BaseModel):
    notes: str | None = None


class TicketActionResponse(BaseModel):
    message: str
    ticket: ConvictionTicketResponse
