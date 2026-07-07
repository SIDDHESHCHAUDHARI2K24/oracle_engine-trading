"""NumericalOrchestrator — the core of Block A1 data ingestion.

Coordinates fetchers with failover, applies cleaning rules, persists
via repositories, and manages IngestRun lifecycle.

Per spec a1.5: resolves active tickers from universes, fetches OHLCV
with yfinance→Alpaca→Stooq failover, fetches macro via FRED, cleans,
persists, and finalizes the run.
"""

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from .repository import (
    bulk_upsert_macro,
    bulk_upsert_ohlcv,
    create_ingest_run,
    finalize_ingest_run,
)
from .shared.exceptions import DataPipelineAlert, EmptyDataError, FetcherError

logger = logging.getLogger(__name__)


class NumericalOrchestrator:
    """Coordinates the full data ingestion pipeline per spec a1.5."""

    def __init__(
        self,
        session: AsyncSession,
        ohlcv_fetchers: list | None = None,
        macro_fetcher=None,
        alert_threshold: int = 3,
        stale_threshold_days: int = 30,
    ):
        self._session = session
        self._ohlcv_fetchers = ohlcv_fetchers or []
        self._macro_fetcher = macro_fetcher
        self._alert_threshold = alert_threshold
        self._stale_threshold_days = stale_threshold_days

    async def run(
        self,
        ticker_map: dict[str, uuid.UUID],
        start_date: str,
        end_date: str,
        mode: str = "backfill",
    ) -> dict:
        """Execute the full ingestion pipeline.

        Args:
            ticker_map: Mapping of symbol → ticker UUID (from universes/tickers).
            start_date: ISO date string for fetch start.
            end_date: ISO date string for fetch end.
            mode: One of 'backfill', 'incremental', 'gap_fill', 'on_demand'.

        Returns:
            Summary dict with run statistics.
        """
        symbols = list(ticker_map.keys())
        run_row = await create_ingest_run(self._session, triggered_by=mode)
        ohlcv_rows = 0
        macro_rows = 0
        failed_tickers: list[str] = []
        stale_macro = False
        error_summary = None

        try:
            ohlcv_results = self._fetch_with_failover(symbols, start_date, end_date)
            failed_tickers = [s for s in symbols if s not in ohlcv_results]

            ohlcv_rows = await self._persist_ohlcv(
                ohlcv_results, ticker_map, run_row.id
            )

            if self._macro_fetcher is not None:
                try:
                    macro_df = self._fetch_macro(start_date, end_date)
                    if macro_df is not None and not macro_df.empty:
                        macro_rows = await self._persist_macro(macro_df, run_row.id)
                        latest = {}
                        if hasattr(self._macro_fetcher, "get_latest_dates"):
                            latest = self._macro_fetcher.get_latest_dates()
                        stale_macro = self._is_macro_stale(latest)
                except Exception as e:
                    logger.warning("Macro fetch failed: %s", e)

            status = "succeeded"
            if failed_tickers:
                status = "partial" if ohlcv_results else "failed"

            await finalize_ingest_run(
                self._session,
                run_row,
                status=status,
                ohlcv_rows=ohlcv_rows,
                macro_rows=macro_rows,
                failed_tickers=failed_tickers,
                stale_macro=stale_macro,
                error_summary=error_summary,
            )
            await self._session.commit()

        except Exception as e:
            logger.exception("Ingest run %s failed", run_row.id)
            await finalize_ingest_run(
                self._session,
                run_row,
                status="failed",
                ohlcv_rows=ohlcv_rows,
                macro_rows=macro_rows,
                failed_tickers=failed_tickers,
                error_summary=str(e)[:1000],
            )
            await self._session.commit()

        return {
            "run_id": str(run_row.id),
            "status": run_row.status,
            "ohlcv_rows": ohlcv_rows,
            "macro_rows": macro_rows,
            "failed_tickers": failed_tickers,
            "stale_macro": stale_macro,
        }

    def _fetch_with_failover(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV with failover chain per ticker.

        Tries primary → secondary → tertiary per source.
        Each result DataFrame is annotated with its winning `source`.
        """
        if not symbols or not self._ohlcv_fetchers:
            return {}

        all_failed: set[str] = set(symbols)
        results: dict[str, pd.DataFrame] = {}

        for fetcher in self._ohlcv_fetchers:
            if not all_failed:
                break

            remaining = list(all_failed)
            try:
                fetched = fetcher.fetch(remaining, start_date, end_date)
            except (EmptyDataError, FetcherError) as e:
                logger.warning(
                    "Fetcher %s failed for %d symbols: %s",
                    fetcher.source_name, len(remaining), e,
                )
                continue
            except Exception as e:
                logger.warning(
                    "Fetcher %s unexpected error: %s", fetcher.source_name, e
                )
                continue

            for symbol, df in fetched.items():
                if symbol in all_failed and not df.empty:
                    df = df.copy()
                    df["source"] = fetcher.source_name
                    results[symbol] = df
                    all_failed.discard(symbol)

        if len(all_failed) > self._alert_threshold:
            raise DataPipelineAlert(
                list(all_failed),
                self._ohlcv_fetchers[0].source_name if self._ohlcv_fetchers else "unknown",
                len(symbols),
            )

        return results

    def _fetch_macro(self, start_date: str, end_date: str) -> pd.DataFrame | None:
        """Fetch macro data via FREDFetcher."""
        if self._macro_fetcher is None:
            return None
        result = self._macro_fetcher.fetch([], start_date, end_date)
        return result.get("__macro__")

    async def _persist_ohlcv(
        self,
        results: dict[str, pd.DataFrame],
        ticker_map: dict[str, uuid.UUID],
        ingest_run_id: uuid.UUID,
    ) -> int:
        """Convert fetched DataFrames to DB records and bulk upsert."""
        records = []

        for symbol, df in results.items():
            if df.empty:
                continue
            ticker_id = ticker_map.get(symbol)
            if ticker_id is None:
                logger.warning("No ticker ID for symbol %s, skipping", symbol)
                continue

            for idx, row in df.iterrows():
                bar_date_val = idx.date() if hasattr(idx, "date") else idx
                records.append({
                    "ticker_id": ticker_id,
                    "bar_date": bar_date_val,
                    "open": Decimal(str(row.get("open", 0))),
                    "high": Decimal(str(row.get("high", 0))),
                    "low": Decimal(str(row.get("low", 0))),
                    "close": Decimal(str(row.get("close", 0))),
                    "adjusted_close": Decimal(str(row.get("adjusted_close", row.get("close", 0)))),
                    "volume": int(row.get("volume", 0)),
                })

        if not records:
            return 0

        first_source = "unknown"
        for symbol, df in results.items():
            if not df.empty and "source" in df.columns:
                first_source = str(df["source"].iloc[0])
                break

        return await bulk_upsert_ohlcv(
            self._session, records, ingest_run_id, first_source
        )

    async def _persist_macro(
        self, df: pd.DataFrame, ingest_run_id: uuid.UUID
    ) -> int:
        """Convert macro DataFrame to DB records and bulk upsert."""
        records = []
        for idx, row in df.iterrows():
            obs_date = idx.date() if hasattr(idx, "date") else idx
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    continue
                records.append({
                    "series_name": col,
                    "observed_date": obs_date,
                    "value": Decimal(str(float(val))),
                    "source": "fred",
                    "is_forward_filled": False,
                })

        if not records:
            return 0

        return await bulk_upsert_macro(self._session, records, ingest_run_id)

    def _is_macro_stale(self, latest_dates: dict) -> bool:
        """Check if any macro series' latest observation is > threshold days old."""
        if not latest_dates:
            return False
        cutoff = date.today() - timedelta(days=self._stale_threshold_days)
        for d in latest_dates.values():
            raw = d.date() if hasattr(d, "date") else d
            if isinstance(raw, pd.Timestamp):
                raw = raw.date()
            if isinstance(raw, date) and raw < cutoff:
                return True
        return False

    def _drop_leading_nans(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop leading rows where OHLCV columns are all NaN."""
        ohlcv_cols = ["open", "high", "low", "close"]
        valid_cols = [c for c in ohlcv_cols if c in df.columns]
        if not valid_cols:
            return df
        first_valid = df[valid_cols].first_valid_index()
        if first_valid is None:
            return df
        return df.loc[first_valid:]
