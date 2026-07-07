from datetime import date, datetime

import numpy as np


def create_walk_forward_split(
    dates: list[date],
    train_frac: float = 0.70,
    calibration_frac: float = 0.15,
) -> tuple[list[date], list[date], list[date]]:
    """Produce a strictly chronological 3-way split with no leakage.

    The calibration and validation sets always follow the training set in
    time.  Returns three date lists suitable for recording on
    ``TrainingRun`` and filtering a ``TimeSeriesDataset``.
    """
    if not dates:
        raise ValueError("dates must not be empty")

    sorted_dates = sorted(set(dates))
    n = len(sorted_dates)

    train_end = int(n * train_frac)
    cal_end = train_end + int(n * calibration_frac)

    train = sorted_dates[:train_end]
    calibration = sorted_dates[train_end:cal_end]
    validation = sorted_dates[cal_end:]

    _validate_no_overlap(train, calibration, "calibration")
    _validate_no_overlap(calibration, validation, "validation")
    _validate_no_overlap(train, validation, "validation")

    return train, calibration, validation


def slide_window_forward(
    dates: list[date],
    trading_days: int = 7,
) -> list[date]:
    """Slide the overall date window forward by ``trading_days``.

    Used by the weekly retrain to advance the 2-year rolling window.
    """
    if not dates:
        return dates
    sorted_dates = sorted(set(dates))
    cutoff = sorted_dates[min(trading_days, len(sorted_dates) - 1)]
    return [d for d in sorted_dates if d > cutoff]


def _validate_no_overlap(
    before: list[date],
    after: list[date],
    label: str,
) -> None:
    if not before or not after:
        return
    max_before = max(before)
    min_after = min(after)
    if max_before >= min_after:
        raise ValueError(
            f"{label} dates overlap or are out of order: "
            f"max(train)={max_before}, min({label})={min_after}"
        )
