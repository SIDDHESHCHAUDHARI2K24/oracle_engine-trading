import uuid


class TestFilterGate:
    """Unit tests for the 4-criteria filter gate logic."""

    def _make_prediction(
        self, ticker_id, horizon_idx, pred, lo, hi, conviction, universe_id=None
    ):
        """Helper to create a prediction-like dict."""
        h = ["t1", "t5", "t10", "t15"][horizon_idx]
        return {
            "ticker_id": ticker_id,
            "universe_id": universe_id or uuid.uuid4(),
            "horizon_key": h,
            "horizon_idx": horizon_idx,
            "pred": pred,
            "pred_lo": lo,
            "pred_hi": hi,
            "conviction": conviction,
            "width": hi - lo,
        }

    def test_conviction_at_threshold_fails(self):
        """Conviction exactly 67 fails; 67.01 passes conviction criterion."""
        from app.features.conviction_tickets.filter.gate import _check_conviction

        assert not _check_conviction(67.0)
        assert _check_conviction(67.01)
        assert not _check_conviction(66.99)

    def test_negative_predicted_return_fails(self):
        """Predicted return <= 0 always fails direction check."""
        from app.features.conviction_tickets.filter.gate import _check_direction

        assert _check_direction(0.01)
        assert not _check_direction(0.0)
        assert not _check_direction(-0.01)

    def test_backtest_pass_count_too_low_fails(self):
        """Less than 2 backtest passes fails the criterion."""
        from app.features.conviction_tickets.filter.gate import _check_backtest

        assert not _check_backtest(0)
        assert not _check_backtest(1)
        assert _check_backtest(2)
        assert _check_backtest(3)
        assert _check_backtest(4)

    def test_conformal_width_exceeds_W_max_fails(self):
        """Width >= W_max fails; width < W_max passes."""
        from app.features.conviction_tickets.filter.gate import _check_width

        assert _check_width(0.03, 0.05)  # 0.03 < 0.05
        assert not _check_width(0.05, 0.05)  # Exactly at threshold fails
        assert not _check_width(0.06, 0.05)  # Exceeds

    def test_all_criteria_pass_emits_ticket(self):
        """When all 4 criteria pass, the filter emits the (ticker, horizon) pair."""
        from app.features.conviction_tickets.filter.gate import evaluate_filter

        predictions = [
            self._make_prediction("t1", 0, 0.02, 0.01, 0.04, 75.0),  # T+1: passes
        ]
        backtest_passes = {"t1": 3}
        w_max = {0: 0.05, 1: 0.08, 2: 0.10, 3: 0.12}

        passes = evaluate_filter(predictions, backtest_passes, w_max)

        assert len(passes) == 1
        assert passes[0]["ticker_id"] == "t1"
        assert passes[0]["horizon_idx"] == 0

    def test_per_horizon_independence(self):
        """T+5 passes but T+10 fails → only one T+5 ticket emitted."""
        from app.features.conviction_tickets.filter.gate import evaluate_filter

        predictions = [
            self._make_prediction(
                "t1", 1, 0.02, 0.01, 0.04, 75.0
            ),  # T+5: passes width 0.03
            self._make_prediction(
                "t1", 2, -0.01, -0.03, 0.00, 80.0
            ),  # T+10: fails direction (neg return)
        ]
        backtest_passes = {"t1": 3}
        w_max = {0: 0.02, 1: 0.10, 2: 0.10, 3: 0.10}

        passes = evaluate_filter(predictions, backtest_passes, w_max)

        assert len(passes) == 1
        assert passes[0]["horizon_idx"] == 1  # Only T+5

    def test_missing_backtest_zero_passes_fails(self):
        """Ticker with no backtest data → 0 passes → fails criterion."""
        from app.features.conviction_tickets.filter.gate import evaluate_filter

        predictions = [
            self._make_prediction("t_new", 1, 0.02, 0.01, 0.04, 80.0),
        ]
        backtest_passes = {}  # t_new not in backtest data
        w_max = {0: 0.02, 1: 0.10, 2: 0.10, 3: 0.10}

        passes = evaluate_filter(predictions, backtest_passes, w_max)

        # 0 backtest passes < 2 → no tickets
        assert len(passes) == 0

    def test_multiple_tickers_multiple_horizons(self):
        """Complex case: multiple tickers with mixed passing horizons."""
        from app.features.conviction_tickets.filter.gate import evaluate_filter

        predictions = [
            # Ticker A: T+5 passes, T+10 passes
            self._make_prediction("A", 1, 0.02, 0.01, 0.04, 80.0),
            self._make_prediction("A", 2, 0.015, 0.005, 0.03, 72.0),
            # Ticker B: T+1 fails conviction, T+5 passes
            self._make_prediction("B", 0, 0.03, 0.02, 0.05, 65.0),
            self._make_prediction("B", 1, 0.02, 0.01, 0.04, 75.0),
        ]
        backtest_passes = {"A": 3, "B": 2}
        w_max = {0: 0.02, 1: 0.10, 2: 0.10, 3: 0.10}

        passes = evaluate_filter(predictions, backtest_passes, w_max)

        # Ticker A/T+5: conviction 80 > 67, return 0.02 > 0, passes 3 >= 2, width 0.03 < 0.10 → PASS
        # Ticker A/T+10: conviction 72 > 67, return 0.015 > 0, passes 3 >= 2, width 0.025 < 0.10 → PASS
        # Ticker B/T+1: conviction 65 < 67 → FAIL
        # Ticker B/T+5: conviction 75 > 67, return 0.02 > 0, passes 2 >= 2, width 0.03 < 0.10 → PASS
        assert len(passes) == 3
        ticker_horizons = {(p["ticker_id"], p["horizon_idx"]) for p in passes}
        assert ("A", 1) in ticker_horizons
        assert ("A", 2) in ticker_horizons
        assert ("B", 1) in ticker_horizons
