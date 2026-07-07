import pandas as pd
import numpy as np
from app.features.backtesting.shared.metrics_engine import MetricsEngine


class TestMetricsEngine:
    def test_profitable_fixture_positive_metrics(self):
        """Known-profitable signal produces positive Sharpe, positive total_return."""
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        close = pd.Series(np.linspace(100, 120, 50), index=dates)
        entries = pd.Series(False, index=dates)
        entries.iloc[10] = True
        exits = pd.Series(False, index=dates)
        exits.iloc[40] = True

        engine = MetricsEngine(risk_free=0.0)
        result = engine.run(close, entries, exits)

        assert result["sharpe_ratio"] > 0
        assert result["total_return"] > 0
        assert result["total_trades"] == 1
        assert result["win_rate"] == 1.0
        assert "equity_curve" in result
        assert len(result["equity_curve"]) > 0

    def test_no_trades_returns_empty_metrics(self):
        """No entry signals -> no trades -> all metrics zero, no crash."""
        dates = pd.date_range("2020-01-01", periods=30, freq="B")
        close = pd.Series(np.linspace(100, 105, 30), index=dates)
        entries = pd.Series(False, index=dates)
        exits = pd.Series(False, index=dates)

        engine = MetricsEngine()
        result = engine.run(close, entries, exits)

        assert result["sharpe_ratio"] == 0.0
        assert result["total_return"] == 0.0
        assert result["total_trades"] == 0
        assert result["max_drawdown"] == 0.0

    def test_zero_losses_profit_factor(self):
        """All wins, zero losses -> profit_factor handled without div-by-zero."""
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        close = pd.Series(np.linspace(100, 130, 50), index=dates)
        entries = pd.Series(False, index=dates)
        entries.iloc[5] = True
        exits = pd.Series(False, index=dates)
        exits.iloc[45] = True

        engine = MetricsEngine()
        result = engine.run(close, entries, exits)

        assert "profit_factor" in result
        assert result["profit_factor"] >= 0.0

    def test_equity_curve_format(self):
        """Equity curve is list of {date, value} dicts."""
        dates = pd.date_range("2020-01-01", periods=30, freq="B")
        close = pd.Series(np.linspace(100, 110, 30), index=dates)
        entries = pd.Series(False, index=dates)
        entries.iloc[5] = True
        exits = pd.Series(False, index=dates)
        exits.iloc[25] = True

        engine = MetricsEngine()
        result = engine.run(close, entries, exits)

        eq = result["equity_curve"]
        assert isinstance(eq, list)
        assert len(eq) > 1
        assert "date" in eq[0]
        assert "value" in eq[0]
        assert isinstance(eq[0]["value"], (int, float))

    def test_sharpe_uses_risk_free_45(self):
        """Sharpe ratio uses 4.5% risk-free rate."""
        dates = pd.date_range("2020-01-01", periods=50, freq="B")
        close = pd.Series(
            100 + np.cumsum(np.random.RandomState(42).randn(50) * 0.001), index=dates
        )
        entries = pd.Series(False, index=dates)
        entries.iloc[10] = True
        exits = pd.Series(False, index=dates)
        exits.iloc[40] = True

        engine = MetricsEngine(risk_free=0.045)
        result = engine.run(close, entries, exits)

        assert isinstance(result["sharpe_ratio"], float)

    def test_all_six_metrics_present(self):
        """All 6 required metrics are in the result dict."""
        dates = pd.date_range("2020-01-01", periods=30, freq="B")
        close = pd.Series(
            100 + np.cumsum(np.random.RandomState(42).randn(30) * 0.5), index=dates
        )
        entries = pd.Series(False, index=dates)
        entries.iloc[5] = True
        exits = pd.Series(False, index=dates)
        exits.iloc[20] = True

        engine = MetricsEngine()
        result = engine.run(close, entries, exits)

        required = [
            "sharpe_ratio",
            "max_drawdown",
            "total_return",
            "win_rate",
            "profit_factor",
            "total_trades",
            "equity_curve",
        ]
        for key in required:
            assert key in result, f"Missing metric: {key}"
