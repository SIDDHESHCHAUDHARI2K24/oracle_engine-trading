import logging
import pickle
import uuid
from dataclasses import dataclass
from datetime import date
from io import BytesIO

import numpy as np
import pandas as pd
import torch
from pytorch_forecasting import TemporalFusionTransformer
from pytorch_forecasting.metrics import QuantileLoss
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.artifact_store import ArtifactStore
from app.features.feature_engineering.models import FeatureMatrix
from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)
from app.features.ml_models import repository
from app.features.ml_models.artifact_service import ArtifactLifecycleService
from app.features.ml_models.conformal.calibrator import ConformalCalibrator
from app.features.ml_models.ensemble.scoring import compute_conviction
from app.features.ml_models.lstm.architecture import LSTMMathEngine
from app.features.ml_models.tft.data_adapter import build_tft_dataset
from app.features.universes.repository import list_active_tickers_for_universe

logger = logging.getLogger(__name__)
LOOKBACK = 252
DEFAULT_MARGIN = 0.02

TARGET_COLUMNS = list(target_names())
FEATURE_COLUMNS = list(input_feature_names())

TFT_ROLE_MAP = {
    "tft_t1": "t1",
    "tft_t5": "t5",
    "tft_t10": "t10",
    "tft_t15": "t15",
}


def _rows_to_dataframe(
    rows: list,
    ticker_id: uuid.UUID,
) -> pd.DataFrame:
    records: list[dict] = []
    for row in rows:
        rec = {"ticker_id": ticker_id, "bar_date": row.bar_date}
        for col in FEATURE_COLUMNS:
            rec[col] = float(getattr(row, col, 0.0) or 0.0)
        for col in TARGET_COLUMNS:
            rec[col] = 0.0
        records.append(rec)
    return pd.DataFrame(records)


def _load_tft_model(artifact_bytes: bytes) -> TemporalFusionTransformer:
    payload = pickle.loads(artifact_bytes)
    dummy_records = [{"ticker_id": uuid.UUID(int=0), "bar_date": date(2020, 1, 1)}]
    for fc in FEATURE_COLUMNS:
        dummy_records[0][fc] = 0.0
    for tc in TARGET_COLUMNS:
        dummy_records[0][tc] = 0.0
    dummy_df = pd.DataFrame(dummy_records)
    dummy_df["bar_date"] = pd.to_datetime(dummy_df["bar_date"])

    ds = build_tft_dataset(dummy_df, target_column="target_t1")
    model = TemporalFusionTransformer.from_dataset(
        ds,
        learning_rate=payload["learning_rate"],
        hidden_size=payload["hidden_size"],
        attention_head_size=payload["attention_head_size"],
        dropout=payload["dropout"],
        hidden_continuous_size=payload["hidden_continuous_size"],
        loss=QuantileLoss([0.1, 0.5, 0.9]),
    )
    state_bytes = BytesIO(payload["state_dict_bytes"])
    model.load_state_dict(torch.load(state_bytes, weights_only=True))
    model.eval()
    return model


def _calibrator_to_bytes(calibrator: ConformalCalibrator) -> bytes:
    buf = BytesIO()
    torch.save(
        {
            "residual_predictor_state": calibrator.residual_predictor.state_dict(),
            "quantiles": calibrator.quantiles,
            "alpha": calibrator.alpha,
        },
        buf,
    )
    return buf.getvalue()


def _load_w_max(conformal_artifact) -> dict[int, float]:
    """Extract W_max from a conformal artifact's model metadata.

    Returns an empty dict if the metadata is absent or the artifact
    predates the W_max backfill (P5.T0).
    """
    meta = conformal_artifact.model_metadata or {}
    w_max_raw = meta.get("w_max", {})
    if not w_max_raw:
        return {}
    return {int(k): float(v) for k, v in w_max_raw.items()}


def _calibrator_from_bytes(data: bytes) -> ConformalCalibrator:
    buf = BytesIO(data)
    checkpoint = torch.load(buf, weights_only=False)
    cal = ConformalCalibrator(alpha=checkpoint["alpha"])
    cal.residual_predictor.load_state_dict(checkpoint["residual_predictor_state"])
    cal.quantiles = checkpoint["quantiles"]
    return cal


@dataclass
class InferenceResult:
    inference_run_id: uuid.UUID
    num_tickers_scored: int
    num_predictions_written: int
    status: str
    error: str | None = None


async def run_inference(
    universe_id: uuid.UUID,
    inference_date: date,
    db_session: AsyncSession,
    artifact_store: ArtifactStore,
) -> InferenceResult:
    lifecycle = ArtifactLifecycleService(artifact_store)
    active_artifacts = await lifecycle.get_active_artifacts(db_session, universe_id)

    if not active_artifacts:
        raise ValueError(
            f"No active artifacts for universe {universe_id}. "
            "Train models before running inference."
        )

    artifact_ids = [a.id for a in active_artifacts]

    lstm_bytes = await lifecycle.load_active(db_session, universe_id, "lstm")
    lstm_model = LSTMMathEngine.deserialize(lstm_bytes)
    lstm_model.eval()

    calibrator: ConformalCalibrator | None = None
    try:
        cal_bytes = await lifecycle.load_active(db_session, universe_id, "conformal")
        calibrator = _calibrator_from_bytes(cal_bytes)
    except (ValueError, KeyError):
        logger.info("No active conformal calibrator — using default margins.")

    tft_models: dict[str, TemporalFusionTransformer | None] = {}
    for role_key in TFT_ROLE_MAP:
        try:
            tft_bytes = await lifecycle.load_active(db_session, universe_id, role_key)
            tft_models[role_key] = _load_tft_model(tft_bytes)
            logger.info("Loaded TFT model for role=%s", role_key)
        except (ValueError, KeyError):
            logger.info(
                "No active TFT artifact for role=%s; using synthetic zeros.", role_key
            )
            tft_models[role_key] = None

    tickers = await list_active_tickers_for_universe(db_session, universe_id)
    feature_cols = input_feature_names()

    predictions: list[dict] = []
    skipped = 0

    inference_run = await repository.create_inference_run(
        db_session, universe_id, "daily_scheduled", inference_date, artifact_ids
    )

    for ticker in tickers:
        result = await db_session.execute(
            select(FeatureMatrix)
            .where(
                FeatureMatrix.ticker_id == ticker.id,
                FeatureMatrix.bar_date <= inference_date,
            )
            .order_by(FeatureMatrix.bar_date.desc())
            .limit(LOOKBACK)
        )
        rows = result.scalars().all()

        if len(rows) < LOOKBACK:
            skipped += 1
            continue

        rows_sorted = sorted(rows, key=lambda r: r.bar_date)
        features = np.array(
            [
                [float(getattr(r, col, 0.0) or 0.0) for col in feature_cols]
                for r in rows_sorted
            ],
            dtype=np.float32,
        )

        x = torch.tensor(features).unsqueeze(0)
        lstm_output = lstm_model.predict(x)
        pred = lstm_output[0].astype(np.float64)

        tft_q10 = np.zeros(4, dtype=np.float64)
        tft_q50 = np.zeros(4, dtype=np.float64)
        tft_q90 = np.zeros(4, dtype=np.float64)
        tft_available = any(m is not None for m in tft_models.values())

        if tft_available:
            predict_df = _rows_to_dataframe(rows_sorted, ticker.id)
            for horizon_label, target_col, role_key in [
                ("t1", "target_t1", "tft_t1"),
                ("t5", "target_t5", "tft_t5"),
                ("t10", "target_t10", "tft_t10"),
                ("t15", "target_t15", "tft_t15"),
            ]:
                model = tft_models.get(role_key)
                if model is None:
                    continue
                try:
                    ds = build_tft_dataset(predict_df, target_column=target_col)
                    loader = ds.to_dataloader(train=False, batch_size=64)
                    tft_preds = model.predict(loader, mode="quantiles")
                    if tft_preds.ndim == 3:
                        tft_preds = tft_preds[0, 0]
                    elif tft_preds.ndim == 2:
                        tft_preds = tft_preds[0]
                    else:
                        tft_preds = np.squeeze(tft_preds)
                    h_idx = ["t1", "t5", "t10", "t15"].index(horizon_label)
                    tft_q10[h_idx] = float(tft_preds[0])
                    tft_q50[h_idx] = float(tft_preds[1])
                    tft_q90[h_idx] = float(tft_preds[2])
                except Exception as exc:
                    logger.warning(
                        "TFT inference failed for ticker=%s horizon=%s: %s",
                        ticker.id,
                        horizon_label,
                        exc,
                    )

        if calibrator is not None:
            last_features = features[-1:].astype(np.float64)
            pred_2d = pred.reshape(1, -1)
            lo, hi = calibrator.predict(pred_2d, last_features)
            pred_lo = lo[0]
            pred_hi = hi[0]
        else:
            pred_lo = pred - DEFAULT_MARGIN
            pred_hi = pred + DEFAULT_MARGIN

        conviction = compute_conviction(
            pred.reshape(1, -1), tft_q10.reshape(1, -1), tft_q90.reshape(1, -1)
        )[0]

        predictions.append(
            {
                "inference_run_id": inference_run.id,
                "ticker_id": ticker.id,
                "universe_id": universe_id,
                "inference_date": inference_date,
                "pred_t1": float(pred[0]),
                "pred_lo_t1": float(pred_lo[0]),
                "pred_hi_t1": float(pred_hi[0]),
                "conviction_t1": float(conviction[0]),
                "pred_t5": float(pred[1]),
                "pred_lo_t5": float(pred_lo[1]),
                "pred_hi_t5": float(pred_hi[1]),
                "conviction_t5": float(conviction[1]),
                "pred_t10": float(pred[2]),
                "pred_lo_t10": float(pred_lo[2]),
                "pred_hi_t10": float(pred_hi[2]),
                "conviction_t10": float(conviction[2]),
                "pred_t15": float(pred[3]),
                "pred_lo_t15": float(pred_lo[3]),
                "pred_hi_t15": float(pred_hi[3]),
                "conviction_t15": float(conviction[3]),
                "lstm_outputs": lstm_output[0].tolist(),
                "tft_q10": tft_q10.tolist(),
                "tft_q50": tft_q50.tolist(),
                "tft_q90": tft_q90.tolist(),
            }
        )

    if skipped:
        logger.info("Skipped %d tickers with < %d days of history.", skipped, LOOKBACK)

    num_written = await repository.upsert_predictions(db_session, predictions)

    await repository.complete_inference_run(
        db_session,
        inference_run.id,
        "completed",
        num_tickers_scored=len(predictions),
    )

    return InferenceResult(
        inference_run_id=inference_run.id,
        num_tickers_scored=len(predictions),
        num_predictions_written=num_written,
        status="completed",
    )
