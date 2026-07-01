"""Backtesting Pydantic v2 schemas."""

from datetime import date, datetime
import uuid

from pydantic import BaseModel, ConfigDict


class BacktestRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    universe_id: uuid.UUID
    triggered_by: str
    backtest_period_start: date
    backtest_period_end: date
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: str
    num_tickers: int | None = None
    num_strategies: int = 4


class TriggerRequest(BaseModel):
    universe_id: uuid.UUID
    ticker_id: uuid.UUID | None = None


class TriggerResponse(BaseModel):
    backtest_run_id: uuid.UUID
    status: str


class StrategyMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_name: str
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    total_return: float | None = None
    win_rate: float | None = None
    profit_factor: float | None = None
    total_trades: int | None = None
    passed: bool = False
    equity_curve: list[dict] | None = None


class TickerBacktestDetail(BaseModel):
    ticker_id: uuid.UUID
    symbol: str
    strategies: list[StrategyMetricsResponse]


class TickerPasses(BaseModel):
    ticker_id: uuid.UUID
    symbol: str
    passes: int
    strategies: dict[str, bool]


class UniversePassSummary(BaseModel):
    universe_id: uuid.UUID
    run: BacktestRunResponse | None = None
    tickers: list[TickerPasses]
