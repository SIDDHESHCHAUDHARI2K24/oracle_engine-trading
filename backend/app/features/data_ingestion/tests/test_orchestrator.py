"""Tests for the NumericalOrchestrator — failover, isolation, cleaning rules."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.features.data_ingestion.shared.exceptions import (
    DataPipelineAlert,
    EmptyDataError,
)


class TestOrchestratorFailover:
    """P2.T5.S1 — Failover chain: yfinance → Alpaca → Stooq."""

    def test_failover_yfinance_to_alpaca(self):
        """When yfinance fails, Alpaca is tried and its source recorded."""
        from app.features.data_ingestion.service import NumericalOrchestrator

        yf = MagicMock()
        yf.source_name = "yahoofinance"
        yf.fetch.side_effect = EmptyDataError("yahoofinance", ["AAPL"])

        alpaca = MagicMock()
        alpaca.source_name = "alpaca"
        df = self._make_ohlcv_df()
        alpaca.fetch.return_value = {"AAPL": df}

        stooq = MagicMock()
        stooq.source_name = "stooq"

        mock_session = MagicMock()
        mock_session.execute = MagicMock()

        orchestrator = NumericalOrchestrator(
            session=mock_session,
            ohlcv_fetchers=[yf, alpaca, stooq],
        )

        results = orchestrator._fetch_with_failover(
            ["AAPL"], "2024-01-01", "2024-01-10"
        )

        yf.fetch.assert_called_once()
        alpaca.fetch.assert_called_once()
        stooq.fetch.assert_not_called()
        assert results["AAPL"]["source"].iloc[0] == "alpaca"

    def test_failover_to_stooq_as_last_resort(self):
        """When yfinance and Alpaca fail, Stooq is the fallback."""
        from app.features.data_ingestion.service import NumericalOrchestrator

        yf = MagicMock()
        yf.source_name = "yahoofinance"
        yf.fetch.side_effect = EmptyDataError("yahoofinance", ["MSFT"])

        alpaca = MagicMock()
        alpaca.source_name = "alpaca"
        alpaca.fetch.side_effect = EmptyDataError("alpaca", ["MSFT"])

        stooq = MagicMock()
        stooq.source_name = "stooq"
        df = self._make_ohlcv_df()
        stooq.fetch.return_value = {"MSFT": df}

        mock_session = MagicMock()
        orchestrator = NumericalOrchestrator(
            session=mock_session,
            ohlcv_fetchers=[yf, alpaca, stooq],
        )

        results = orchestrator._fetch_with_failover(
            ["MSFT"], "2024-01-01", "2024-01-10"
        )

        yf.fetch.assert_called_once()
        alpaca.fetch.assert_called_once()
        stooq.fetch.assert_called_once()
        assert results["MSFT"]["source"].iloc[0] == "stooq"

    @staticmethod
    def _make_ohlcv_df() -> pd.DataFrame:
        dates = pd.date_range("2024-01-02", "2024-01-10", freq="B")
        return pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [105.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [102.0] * len(dates),
                "adjusted_close": [102.0] * len(dates),
                "volume": [1000000] * len(dates),
            },
            index=dates,
        )


class TestOrchestratorIsolation:
    """P2.T5.S1 — Per-ticker isolation: one failure doesn't abort the batch."""

    def test_one_ticker_failure_does_not_abort_batch(self):
        """AAPL fails all sources, MSFT succeeds — MSFT still returns."""
        from app.features.data_ingestion.service import NumericalOrchestrator

        yf = MagicMock()
        yf.source_name = "yahoofinance"
        df = TestOrchestratorFailover._make_ohlcv_df()

        def mock_fetch(symbols, start, end):
            if "AAPL" in symbols and "MSFT" in symbols:
                return {"MSFT": df.copy()}
            if symbols == ["AAPL"]:
                raise EmptyDataError("yahoofinance", ["AAPL"])
            return {"MSFT": df.copy()}

        yf.fetch.side_effect = mock_fetch

        alpaca = MagicMock()
        alpaca.source_name = "alpaca"
        alpaca.fetch.side_effect = EmptyDataError("alpaca", ["AAPL"])

        stooq = MagicMock()
        stooq.source_name = "stooq"
        stooq.fetch.side_effect = EmptyDataError("stooq", ["AAPL"])

        mock_session = MagicMock()
        orchestrator = NumericalOrchestrator(
            session=mock_session,
            ohlcv_fetchers=[yf, alpaca, stooq],
        )

        results = orchestrator._fetch_with_failover(
            ["AAPL", "MSFT"], "2024-01-01", "2024-01-10"
        )

        assert "MSFT" in results
        assert "AAPL" not in results

    def test_ticker_count_exceeds_alert_threshold(self):
        """When >3 tickers fail, DataPipelineAlert is raised."""
        from app.features.data_ingestion.service import NumericalOrchestrator

        yf = MagicMock()
        yf.source_name = "yahoofinance"
        yf.fetch.side_effect = EmptyDataError("yahoofinance", ["A", "B", "C", "D"])

        alpaca = MagicMock()
        alpaca.source_name = "alpaca"
        alpaca.fetch.side_effect = EmptyDataError("alpaca", ["A", "B", "C", "D"])

        stooq = MagicMock()
        stooq.source_name = "stooq"
        stooq.fetch.side_effect = EmptyDataError("stooq", ["A", "B", "C", "D"])

        mock_session = MagicMock()
        orchestrator = NumericalOrchestrator(
            session=mock_session,
            ohlcv_fetchers=[yf, alpaca, stooq],
            alert_threshold=3,
        )

        with pytest.raises(DataPipelineAlert) as exc_info:
            orchestrator._fetch_with_failover(
                ["A", "B", "C", "D"], "2024-01-01", "2024-01-10"
            )

        assert len(exc_info.value.failed_tickers) == 4


class TestOrchestratorCleaning:
    """P2.T5.S1 — Data cleaning rules."""

    def test_macro_stale_flag_when_series_old(self):
        """stale_macro=True when latest observation >30 days old."""
        from datetime import timedelta

        from app.features.data_ingestion.service import NumericalOrchestrator

        old_date = date.today() - timedelta(days=40)
        orchestrator = NumericalOrchestrator.__new__(NumericalOrchestrator)
        orchestrator._stale_threshold_days = 30

        latest_dates = {"fed_funds_rate": old_date}
        assert orchestrator._is_macro_stale(latest_dates) is True

    def test_macro_not_stale_when_fresh(self):
        """stale_macro=False when all series <=30 days old."""
        from datetime import timedelta

        from app.features.data_ingestion.service import NumericalOrchestrator

        fresh_date = date.today() - timedelta(days=5)
        orchestrator = NumericalOrchestrator.__new__(NumericalOrchestrator)
        orchestrator._stale_threshold_days = 30

        latest_dates = {"fed_funds_rate": fresh_date, "cpi": fresh_date}
        assert orchestrator._is_macro_stale(latest_dates) is False

    def test_leading_nan_drop(self):
        """Leading NaN rows in a DataFrame are dropped after merge."""
        import numpy as np

        from app.features.data_ingestion.service import NumericalOrchestrator

        df = pd.DataFrame(
            {
                "open": [np.nan, np.nan, 100.0, 101.0],
                "high": [np.nan, np.nan, 105.0, 106.0],
                "low": [np.nan, np.nan, 99.0, 100.0],
                "close": [np.nan, np.nan, 102.0, 103.0],
                "volume": [0, 0, 1000000, 1100000],
                "fed_funds_rate": [5.0, 5.0, 5.0, 5.0],
            },
            index=pd.date_range("2024-01-01", periods=4),
        )

        orchestrator = NumericalOrchestrator.__new__(NumericalOrchestrator)
        cleaned = orchestrator._drop_leading_nans(df)

        assert len(cleaned) == 2
        assert cleaned.iloc[0]["open"] == 100.0
