"""BacktestOrchestrator — runs backtests across tickers and strategies."""

from datetime import date
import logging
import uuid

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.backtesting.models import BacktestRun
from app.features.backtesting.repository import (
    complete_backtest_run,
    create_backtest_run,
    upsert_backtest_metrics,
)
from app.features.backtesting.shared.base import BaseStrategy
from app.features.backtesting.shared.metrics_engine import MetricsEngine
from app.features.backtesting.strategies.mean_reversion import MeanReversion
from app.features.backtesting.strategies.momentum_cross import MomentumCross
from app.features.backtesting.strategies.volatility_breakout import VolatilityBreakout
from app.features.backtesting.strategies.stat_arb import StatArb
from app.features.data_ingestion.models import OHLCVBar
from app.features.feature_engineering.models import FeatureMatrix
from app.features.feature_engineering.shared.feature_schema import (
    FEATURE_SCHEMA_VERSION,
)
from app.features.universes.models import Ticker
from app.features.universes.repository import list_active_tickers_for_universe

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = ["close", "bb_lower", "bb_middle", "sma_50", "sma_200", "atr_14"]


class BacktestOrchestrator:
    def __init__(self, metrics_engine: MetricsEngine | None = None):
        self.strategies: dict[str, BaseStrategy] = {
            "mean_reversion": MeanReversion(),
            "momentum_cross": MomentumCross(),
            "volatility_breakout": VolatilityBreakout(),
            "stat_arb": StatArb(),
        }
        self.metrics = metrics_engine or MetricsEngine()

    async def _find_spy_ticker(self, session: AsyncSession) -> uuid.UUID | None:
        stmt = select(Ticker.id).where(
            Ticker.symbol == "SPY",
            Ticker.deleted_at.is_(None),  # type: ignore[attr-defined]
        )
        result = await session.execute(stmt)
        row = result.first()
        return row[0] if row else None

    async def run_universe(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
        period_start: date,
        period_end: date,
        triggered_by: str = "on_demand",
    ) -> BacktestRun:
        tickers = await list_active_tickers_for_universe(session, universe_id)
        spy_ticker_id = await self._find_spy_ticker(session)

        spy_close: pd.Series | None = None
        if spy_ticker_id is not None:
            spy_bars = await _get_ohlcv_close(
                session, spy_ticker_id, period_start, period_end
            )
            spy_close = _bars_to_series(spy_bars)

        run = await create_backtest_run(
            session, universe_id, triggered_by, period_start, period_end
        )

        all_metrics: list[dict] = []
        errors: list[str] = []

        for ticker in tickers:
            try:
                metrics = await self._backtest_ticker(
                    session, run.id, ticker, period_start, period_end, spy_close
                )
                all_metrics.extend(metrics)
            except Exception as e:
                logger.error(f"Backtest failed for ticker {ticker.symbol}: {e}")
                errors.append(str(e))

        if all_metrics:
            await upsert_backtest_metrics(session, all_metrics)

        completed = await complete_backtest_run(
            session,
            run.id,
            status="completed" if len(errors) == 0 else "completed_with_errors",
            num_tickers=len(tickers),
            error="; ".join(errors) if errors else None,
        )
        await session.commit()

        logger.info(
            "Backtest run %s complete: %d tickers, %d metrics, %d errors",
            run.id,
            len(tickers),
            len(all_metrics),
            len(errors),
        )
        return completed

    async def run_single_ticker(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
        ticker_id: uuid.UUID,
        period_start: date,
        period_end: date,
        triggered_by: str = "on_demand",
    ) -> BacktestRun:
        stmt = select(Ticker).where(Ticker.id == ticker_id, Ticker.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await session.execute(stmt)
        ticker = result.scalar_one_or_none()
        if ticker is None:
            raise ValueError(f"Ticker {ticker_id} not found")

        spy_ticker_id = await self._find_spy_ticker(session)
        spy_close: pd.Series | None = None
        if spy_ticker_id is not None:
            spy_bars = await _get_ohlcv_close(
                session, spy_ticker_id, period_start, period_end
            )
            spy_close = _bars_to_series(spy_bars)

        run = await create_backtest_run(
            session, universe_id, triggered_by, period_start, period_end
        )

        try:
            metrics = await self._backtest_ticker(
                session, run.id, ticker, period_start, period_end, spy_close
            )
            if metrics:
                await upsert_backtest_metrics(session, metrics)
            completed = await complete_backtest_run(
                session, run.id, status="completed", num_tickers=1
            )
        except Exception as e:
            logger.error(f"Backtest failed for ticker {ticker.symbol}: {e}")
            completed = await complete_backtest_run(
                session, run.id, status="failed", num_tickers=0, error=str(e)
            )

        await session.commit()
        return completed

    async def _backtest_ticker(
        self,
        session: AsyncSession,
        run_id: uuid.UUID,
        ticker: Ticker,
        period_start: date,
        period_end: date,
        spy_close: pd.Series | None = None,
    ) -> list[dict]:
        stmt = (
            select(FeatureMatrix)
            .where(
                FeatureMatrix.ticker_id == ticker.id,
                FeatureMatrix.bar_date >= period_start,
                FeatureMatrix.bar_date <= period_end,
                FeatureMatrix.feature_schema_version == FEATURE_SCHEMA_VERSION,
            )
            .order_by(FeatureMatrix.bar_date)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return []

        dates = [r.bar_date for r in rows]
        data = {}
        for col in FEATURE_COLUMNS:
            data[col] = [
                float(getattr(r, col)) if getattr(r, col) is not None else np.nan
                for r in rows
            ]
        df = pd.DataFrame(data, index=pd.DatetimeIndex(dates)).sort_index()

        if spy_close is not None and not spy_close.empty:
            df = df.join(spy_close.rename("spy_close"), how="left")

        metrics_records: list[dict] = []
        for strategy_name, strategy in self.strategies.items():
            if strategy_name == "stat_arb" and "spy_close" not in df.columns:
                continue

            try:
                entries, exits = strategy.generate_signals(df)
                result = self.metrics.run(df["close"], entries, exits)  # type: ignore[assignment]

                metrics_records.append(
                    {
                        "backtest_run_id": run_id,
                        "ticker_id": ticker.id,
                        "strategy_name": strategy_name,
                        "sharpe_ratio": result["sharpe_ratio"],  # type: ignore[index]
                        "max_drawdown": result["max_drawdown"],  # type: ignore[index]
                        "total_return": result["total_return"],  # type: ignore[index]
                        "win_rate": result["win_rate"],  # type: ignore[index]
                        "profit_factor": result["profit_factor"],  # type: ignore[index]
                        "total_trades": result["total_trades"],  # type: ignore[index]
                        "equity_curve": result["equity_curve"],  # type: ignore[index]
                    }
                )
            except Exception as e:
                logger.error(
                    "Strategy %s failed for ticker %s: %s",
                    strategy_name,
                    ticker.symbol,
                    e,
                )

        return metrics_records


async def _get_ohlcv_close(
    session: AsyncSession,
    ticker_id: uuid.UUID,
    start: date,
    end: date,
) -> list:
    stmt = (
        select(OHLCVBar)
        .where(
            OHLCVBar.ticker_id == ticker_id,
            OHLCVBar.bar_date >= start,
            OHLCVBar.bar_date <= end,
        )
        .order_by(OHLCVBar.bar_date)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _bars_to_series(bars: list) -> pd.Series:
    if not bars:
        return pd.Series(dtype=float)
    return pd.Series(
        [float(b.close) for b in bars],
        index=pd.DatetimeIndex([b.bar_date for b in bars]),
    ).sort_index()
