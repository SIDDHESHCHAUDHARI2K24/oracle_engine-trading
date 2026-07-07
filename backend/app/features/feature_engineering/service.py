"""FeatureOrchestrator — per-ticker feature pipeline with parallelization.

Orchestrates the full Block A2 + A3 pipeline for one or many tickers:
  technical engine → macro merge → target generation → scaler → sanitize → persist.

Supports two modes:
  - Full recompute: runs on entire OHLCV history for every ticker.
  - Incremental (trailing-window-seeded): finds latest persisted date,
    loads 252 trading days of seed data via the trading calendar (NOT naive
    row counts), runs the pipeline on seed+new data, and persists only new
    rows.  This prevents silent indicator corruption from a too-short seed
    window.
"""

import logging
import uuid as _uuid
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.features.feature_engineering.alignment.macro_merger import MacroMerger
from app.features.feature_engineering.repository import (
    bulk_upsert_feature_matrix,
    bulk_upsert_normalization_stats,
    get_latest_feature_date,
)
from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)
from app.features.feature_engineering.technical.equity_engineer import (
    EquityFeatureEngineer,
)
from app.features.feature_engineering.tensor_prep.feature_scaler import FeatureScaler
from app.features.feature_engineering.tensor_prep.target_generator import (
    TargetGenerator,
)
from app.features.data_ingestion.shared.trading_calendar import last_n_trading_days

logger = logging.getLogger(__name__)


class FeatureOrchestrator:
    """Orchestrate feature computation for one or many tickers.

    Usage:
        orch = FeatureOrchestrator()
        await orch.process_tickers(session, ticker_ids, ohlcv_loader, macro_df)
    """

    def __init__(self, n_jobs: int = -1):
        self.n_jobs = n_jobs
        self.engineer = EquityFeatureEngineer()
        self.merger = MacroMerger()
        self.target_gen = TargetGenerator()
        self.scaler = FeatureScaler()

    def _process_single_ticker(
        self,
        ticker_id: str,
        ohlcv_df: pd.DataFrame,
        macro_df: pd.DataFrame,
    ) -> tuple[list[dict], list[dict], str | None]:
        """Pure function: compute features for one ticker, return (feature_rows, stats_rows, error)."""
        try:
            if ohlcv_df.empty:
                return [], [], None

            ohlcv_df = ohlcv_df.sort_index()

            engineered = self.engineer.generate_features(ohlcv_df)
            merged = self.merger.merge(engineered, macro_df)
            targets = self.target_gen.generate(merged["close"])
            full = merged.join(targets)

            scaled, stats = self.scaler.fit_transform(ticker_id, full)

            full[target_names()] = scaled[target_names()]
            for col in input_feature_names():
                if col in scaled.columns:
                    full[col] = scaled[col]

            # Sanitize per spec a2.6
            feature_cols = [c for c in input_feature_names() if c in full.columns]
            full[feature_cols] = full[feature_cols].replace([np.inf, -np.inf], np.nan)
            full = full.dropna(subset=feature_cols)

            all_expected = input_feature_names() + target_names()
            present = [c for c in all_expected if c in full.columns]
            assert len(present) == len(all_expected), (
                f"Schema assert failed: {len(present)}/{len(all_expected)} columns"
            )

            feature_rows = []
            for idx, row in full.iterrows():
                record = {"ticker_id": ticker_id, "bar_date": idx}
                for col in present:
                    val = row[col]
                    if pd.isna(val):
                        record[col] = None
                    else:
                        record[col] = float(val)
                feature_rows.append(record)

            return feature_rows, stats, None

        except Exception as e:
            logger.error(f"Failed ticker {ticker_id}: {e}")
            return [], [], str(e)

    async def process_tickers(
        self,
        session: AsyncSession,
        ticker_ids: list[Any],
        load_ohlcv,
        macro_df: pd.DataFrame,
    ) -> dict:
        """Process all tickers with per-ticker isolation.

        Args:
            session: Async DB session (used for persistence after computation).
            ticker_ids: List of ticker identifiers (UUIDs or strings).
            load_ohlcv: Callable(ticker_id) → pd.DataFrame with OHLCV bars.
            macro_df: Shared macro DataFrame (read-only).
        """
        ticker_id_strs = [str(t) for t in ticker_ids]
        results = Parallel(n_jobs=self.n_jobs)(
            delayed(self._process_single_ticker)(tid, load_ohlcv(tid), macro_df.copy())
            for tid in ticker_id_strs
        )

        total_features = 0
        total_stats = 0
        errors: list[str] = []

        for feature_rows, stats_rows, error in results:
            if error:
                errors.append(error)
                continue
            total_features += await bulk_upsert_feature_matrix(session, feature_rows)
            total_stats += await bulk_upsert_normalization_stats(session, stats_rows)

        await session.commit()

        return {
            "features_upserted": total_features,
            "stats_upserted": total_stats,
            "errors": errors,
            "tickers_processed": len(ticker_ids),
        }

    async def process_tickers_incremental(
        self,
        session: AsyncSession,
        ticker_ids: list[Any],
        load_ohlcv_range,  # callable(ticker_id, start_date, end_date) -> DataFrame
        macro_df: pd.DataFrame,
        seed_trading_days: int = 252,
    ) -> dict:
        """Incremental: seed trailing window via trading calendar, write only new rows.

        The seed window is computed using the NYSE trading calendar
        (last_n_trading_days), NOT naive row counts. This is the key
        protection against silent indicator corruption (R2).

        Args:
            session: Async DB session for persistence.
            ticker_ids: Ticker identifiers.
            load_ohlcv_range: Async callable(ticker_id, start, end) → DataFrame.
            macro_df: Shared macro DataFrame (read-only).
            seed_trading_days: Size of trailing seed window in trading days.
        """
        from app.features.feature_engineering.repository import (
            delete_feature_rows_for_ticker,
        )

        total_features = 0
        total_stats = 0
        errors: list[str] = []
        processed = 0

        for ticker_id in ticker_ids:
            tid_str = str(ticker_id)
            try:
                latest = await get_latest_feature_date(session, _uuid.UUID(tid_str))

                if latest is None:
                    start_date = date(2010, 1, 1)
                else:
                    seed_dates = last_n_trading_days(seed_trading_days, latest)
                    if seed_dates:
                        start_date = seed_dates[0]
                    else:
                        start_date = latest

                end_date = date.today()
                ohlcv_df = await load_ohlcv_range(ticker_id, start_date, end_date)

                if ohlcv_df is None or ohlcv_df.empty:
                    continue

                feature_rows, stats_rows, error = self._process_single_ticker(
                    tid_str, ohlcv_df, macro_df.copy()
                )
                if error:
                    errors.append(error)
                    continue

                if latest is not None:
                    from_date = latest + pd.Timedelta(days=1)
                    if isinstance(from_date, pd.Timestamp):
                        from_date = from_date.date()
                    await delete_feature_rows_for_ticker(
                        session, _uuid.UUID(tid_str), from_date
                    )

                total_features += await bulk_upsert_feature_matrix(
                    session, feature_rows
                )
                total_stats += await bulk_upsert_normalization_stats(
                    session, stats_rows
                )
                processed += 1

            except Exception as e:
                logger.error(f"Incremental failed for ticker {tid_str}: {e}")
                errors.append(str(e))

        await session.commit()

        return {
            "mode": "incremental",
            "features_upserted": total_features,
            "stats_upserted": total_stats,
            "errors": errors,
            "tickers_processed": processed,
        }


async def get_active_tickers(session: AsyncSession) -> list[dict]:
    """Return all active tickers with their IDs."""
    from app.features.universes.models import Ticker

    stmt = select(Ticker.id, Ticker.symbol).where(
        Ticker.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    return [{"id": str(row[0]), "symbol": row[1]} for row in result.fetchall()]
