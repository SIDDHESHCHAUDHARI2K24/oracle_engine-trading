"""Backtesting REST endpoints."""

from datetime import date
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.backtesting.repository import (
    get_latest_backtest_run,
    get_latest_metrics_for_ticker,
    get_pass_summary,
)
from app.features.backtesting.schemas import (
    BacktestRunResponse,
    TickerBacktestDetail,
    TriggerRequest,
    TriggerResponse,
    UniversePassSummary,
)
from app.features.backtesting.service import BacktestOrchestrator
from app.features.core.database import get_async_session
from app.features.universes.models import Ticker
from sqlalchemy import select

router = APIRouter()

_orchestrator = BacktestOrchestrator()


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_backtest(
    request: TriggerRequest,
    session: AsyncSession = Depends(get_async_session),
    _=Depends(requires_role(["admin"])),
) -> TriggerResponse:
    today = date.today()
    period_start = date(2010, 1, 1)

    if request.ticker_id is not None:
        run = await _orchestrator.run_single_ticker(
            session,
            request.universe_id,
            request.ticker_id,
            period_start,
            today,
        )
    else:
        run = await _orchestrator.run_universe(
            session,
            request.universe_id,
            period_start,
            today,
        )

    return TriggerResponse(backtest_run_id=run.id, status=run.status)


@router.get("/{universe_id}", response_model=UniversePassSummary)
async def get_universe_backtest(
    universe_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> UniversePassSummary:
    latest_run = await get_latest_backtest_run(session, universe_id)
    run_response: BacktestRunResponse | None = None

    if latest_run is not None:
        run_response = BacktestRunResponse.model_validate(latest_run)
        tickers = await get_pass_summary(session, universe_id, run_id=latest_run.id)
        return UniversePassSummary(
            universe_id=universe_id,
            run=run_response,
            tickers=[
                {  # type: ignore[misc]
                    "ticker_id": uuid.UUID(t["ticker_id"]),
                    "symbol": t["symbol"],
                    "passes": t["passes"],
                    "strategies": t["strategies"],
                }
                for t in tickers
            ],
        )

    return UniversePassSummary(universe_id=universe_id, run=None, tickers=[])


@router.get("/{universe_id}/{ticker_id}", response_model=TickerBacktestDetail)
async def get_ticker_backtest_detail(
    universe_id: uuid.UUID,
    ticker_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> TickerBacktestDetail:
    metrics = await get_latest_metrics_for_ticker(session, ticker_id, universe_id)

    if not metrics:
        stmt = select(Ticker.symbol).where(Ticker.id == ticker_id)
        result = await session.execute(stmt)
        symbol = result.scalar_one_or_none()
        if symbol is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "TICKER_NOT_FOUND",
                    "message": "Ticker not found",
                },
            )
        return TickerBacktestDetail(ticker_id=ticker_id, symbol=symbol, strategies=[])

    stmt = select(Ticker.symbol).where(Ticker.id == ticker_id)
    result = await session.execute(stmt)
    symbol_row = result.scalar_one_or_none()
    symbol = symbol_row if symbol_row else str(ticker_id)

    strategies = [
        {
            "strategy_name": m.strategy_name,
            "sharpe_ratio": m.sharpe_ratio,
            "max_drawdown": m.max_drawdown,
            "total_return": m.total_return,
            "win_rate": m.win_rate,
            "profit_factor": m.profit_factor,
            "total_trades": m.total_trades,
            "passed": m.passed,
            "equity_curve": m.equity_curve,
        }
        for m in metrics
    ]

    return TickerBacktestDetail(
        ticker_id=ticker_id, symbol=symbol, strategies=strategies  # type: ignore[arg-type]
    )
