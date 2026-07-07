import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest

_WF_PATH = Path(__file__).resolve().parent.parent / "walk_forward.py"
_spec = importlib.util.spec_from_file_location("walk_forward", _WF_PATH)
_wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wf)
create_walk_forward_split = _wf.create_walk_forward_split
slide_window_forward = _wf.slide_window_forward


def _date_range(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


class TestCreateWalkForwardSplit:
    def test_ratio_70_15_15_for_100_dates(self):
        dates = _date_range(date(2024, 1, 1), 100)
        train, calibration, validation = create_walk_forward_split(dates)

        assert len(train) == 70
        assert len(calibration) == 15
        assert len(validation) == 15

    def test_calibration_follows_training_chronologically(self):
        dates = _date_range(date(2024, 1, 1), 100)
        train, calibration, _ = create_walk_forward_split(dates)

        assert max(train) < min(calibration)

    def test_validation_follows_calibration_chronologically(self):
        dates = _date_range(date(2024, 1, 1), 100)
        _, calibration, validation = create_walk_forward_split(dates)

        assert max(calibration) < min(validation)

    def test_no_overlapping_dates_between_splits(self):
        dates = _date_range(date(2024, 1, 1), 100)
        train, calibration, validation = create_walk_forward_split(dates)

        train_set = set(train)
        cal_set = set(calibration)
        val_set = set(validation)

        assert train_set.isdisjoint(cal_set)
        assert cal_set.isdisjoint(val_set)
        assert train_set.isdisjoint(val_set)

    def test_empty_dates_raises_value_error(self):
        with pytest.raises(ValueError, match="dates must not be empty"):
            create_walk_forward_split([])

    def test_single_date_does_not_raise(self):
        dates = _date_range(date(2024, 6, 1), 1)
        train, calibration, validation = create_walk_forward_split(dates)

        assert len(train) + len(calibration) + len(validation) == 1
        assert len(validation) == 1


class TestSlideWindowForward:
    def test_moves_cutoff_forward_by_7_trading_days(self):
        dates = _date_range(date(2024, 1, 1), 30)
        result = slide_window_forward(dates, trading_days=7)

        min_result = min(result)
        cutoff_date = sorted(set(dates))[min(7, len(dates) - 1)]
        assert min_result > cutoff_date

    def test_empty_dates_returns_empty(self):
        assert slide_window_forward([]) == []
        assert slide_window_forward([], trading_days=7) == []

    def test_window_smaller_than_trading_days_returns_empty(self):
        dates = _date_range(date(2024, 1, 1), 3)
        result = slide_window_forward(dates, trading_days=7)
        assert result == []
