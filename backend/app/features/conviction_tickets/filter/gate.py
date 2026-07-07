"""Filter gate — applies 4 locked criteria to determine which predictions become conviction tickets."""

from typing import Any


def _check_conviction(score: float) -> bool:
    """Conviction score must be strictly greater than 67."""
    return score > 67


def _check_direction(predicted_return: float) -> bool:
    """Long-only: predicted return must be strictly positive."""
    return predicted_return > 0


def _check_backtest(passes: int) -> bool:
    """At least 2 of 4 backtest strategies must pass."""
    return passes >= 2


def _check_width(width: float, w_max: float) -> bool:
    """Conformal interval width must be strictly less than W_max."""
    return width < w_max


def evaluate_filter(
    predictions: list[dict[str, Any]],
    backtest_passes: dict[str, int],
    w_max: dict[int, float],
) -> list[dict[str, Any]]:
    """
    Apply the 4-criteria filter gate to a set of predictions.

    Args:
        predictions: List of prediction dicts with keys:
            ticker_id, horizon_idx, pred, pred_lo, pred_hi, conviction, universe_id
        backtest_passes: Dict[str, int] mapping ticker_id → number of strategies passed
        w_max: Dict[int, float] mapping horizon_idx → W_max width threshold

    Returns:
        List of passing (ticker_id, horizon_idx) pairs that meet all 4 criteria.
    """
    passing = []

    for p in predictions:
        ticker_id = str(p["ticker_id"])
        horizon_idx = p["horizon_idx"]
        conviction = p["conviction"]
        pred = p["pred"]
        width = p["width"]
        bt_passes = backtest_passes.get(ticker_id, 0)
        w = w_max.get(horizon_idx, 0.10)  # default W_max if not specified

        if (
            _check_conviction(conviction)
            and _check_direction(pred)
            and _check_backtest(bt_passes)
            and _check_width(width, w)
        ):
            passing.append(
                {
                    "ticker_id": ticker_id,
                    "horizon_idx": horizon_idx,
                    "pred": pred,
                    "conviction": conviction,
                    "width": width,
                    "backtest_passes": bt_passes,
                    "pred_lo": p.get("pred_lo", 0),
                    "pred_hi": p.get("pred_hi", 0),
                    "universe_id": p.get("universe_id"),
                }
            )

    return passing
