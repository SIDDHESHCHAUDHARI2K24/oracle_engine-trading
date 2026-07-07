from __future__ import annotations

import logging
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)

HORIZON_LABELS = ("t1", "t5", "t10", "t15")


def compute_realized_coverage(
    predictions: list[dict],
    actuals: list[dict],
    lo_key: str = "pred_lo",
    hi_key: str = "pred_hi",
) -> float:
    total = 0
    inside = 0

    for pred, actual in zip(predictions, actuals):
        for h in HORIZON_LABELS:
            lo = pred.get(f"{lo_key}_{h}")
            hi = pred.get(f"{hi_key}_{h}")
            target = actual.get(f"target_{h}")
            if lo is None or hi is None or target is None:
                continue
            total += 1
            if lo <= target <= hi:
                inside += 1

    if total == 0:
        return float("nan")
    return inside / total


def compute_rolling_coverage(
    predictions: list[dict],
    actuals: list[dict],
    window: int = 30,
) -> list[tuple]:
    n = min(len(predictions), len(actuals))
    if n == 0:
        return []

    row_coverages = []
    for i in range(n):
        pred = predictions[i]
        actual = actuals[i]
        row_total = 0
        row_inside = 0
        for h in HORIZON_LABELS:
            lo = pred.get(f"pred_lo_{h}")
            hi = pred.get(f"pred_hi_{h}")
            target = actual.get(f"target_{h}")
            if lo is None or hi is None or target is None:
                continue
            row_total += 1
            if lo <= target <= hi:
                row_inside += 1
        row_coverages.append(row_inside / row_total if row_total > 0 else float("nan"))

    results = []
    buffer: deque[float] = deque(maxlen=window)

    for i, cov in enumerate(row_coverages):
        if not np.isnan(cov):
            buffer.append(cov)
        avg = float(np.mean(buffer)) if buffer else float("nan")
        date_label = predictions[i].get("date") or actuals[i].get("date") or i
        results.append((date_label, avg))

    return results


def check_breach(
    recent_coverages: list[float],
    threshold: float = 0.80,
    sustained_periods: int = 5,
) -> bool:
    if len(recent_coverages) < sustained_periods:
        return False

    tail = recent_coverages[-sustained_periods:]
    return all(c < threshold for c in tail)
