import logging
import pickle
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from torch.utils.data import DataLoader, TensorDataset

from app.core.services.artifact_store import ArtifactStore
from app.core.services.torch_device import set_seed
from app.features.feature_engineering.models import FeatureMatrix
from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)
from app.features.ml_models import repository as ml_repo
from app.features.ml_models.artifact_service import ArtifactLifecycleService
from app.features.ml_models.conformal.calibrator import ConformalCalibrator
from app.features.ml_models.lstm.architecture import LSTMMathEngine
from app.features.ml_models.lstm.trainer import LSTMTrainer
from app.features.ml_models.shared.walk_forward import create_walk_forward_split
from app.features.ml_models.tft.architecture import TemporalFusionQuadArray
from app.features.ml_models.tft.data_adapter import build_tft_dataset
from app.features.universes.models import Ticker, Universe, UniverseMembership

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = list(input_feature_names())
TARGET_COLUMNS = list(target_names())
SEQUENCE_LENGTH = 252
N_FEATURES = 31
N_TARGETS = 4

DEFAULT_HYPERPARAMS = {
    "batch_size": 256,
    "max_epochs": 100,
    "tft_max_epochs": 50,
    "lr": 1e-3,
    "weight_decay": 1e-4,
    "patience": 10,
    "lr_patience": 5,
    "lr_factor": 0.5,
    "alpha": 0.10,
    "residual_epochs": 200,
    "residual_patience": 20,
}

MODEL_ROLES = (
    "lstm",
    "tft_t1",
    "tft_t5",
    "tft_t10",
    "tft_t15",
    "conformal",
    "residual_predictor",
)


@dataclass
class TrainingResult:
    training_run_id: uuid.UUID
    artifact_ids: list[uuid.UUID]
    validation_metrics: dict
    per_epoch_losses: list[dict]
    status: str
    error: str | None = None


def _to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    return float(val)


def _row_to_feature_vector(row) -> np.ndarray:
    return np.array(
        [_to_float(getattr(row, c, 0.0)) for c in FEATURE_COLUMNS], dtype=np.float32
    )


def _row_to_target_vector(row) -> np.ndarray:
    targets = [_to_float(getattr(row, c, None)) for c in TARGET_COLUMNS]
    if any(t is None for t in targets):
        return np.zeros(N_TARGETS, dtype=np.float32)
    return np.array(targets, dtype=np.float32)


async def _fetch_active_ticker_ids(
    session: AsyncSession, universe_id: uuid.UUID
) -> list[uuid.UUID]:
    stmt = (
        select(Ticker.id)
        .join(UniverseMembership, UniverseMembership.ticker_id == Ticker.id)
        .where(
            UniverseMembership.universe_id == universe_id,
            UniverseMembership.removed_at.is_(None),
            Ticker.active.is_(True),
        )
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def _fetch_universe_name(session: AsyncSession, universe_id: uuid.UUID) -> str:
    result = await session.execute(
        select(Universe.name).where(Universe.id == universe_id)
    )
    name = result.scalar_one_or_none()
    return name if name else str(universe_id)


def _universe_slug(universe_name: str) -> str:
    return universe_name.lower().replace(" ", "-").replace("_", "-")


async def _build_training_data(
    session: AsyncSession,
    ticker_ids: list[uuid.UUID],
) -> tuple[np.ndarray, np.ndarray, list[date], pd.DataFrame]:
    if not ticker_ids:
        raise ValueError("No active tickers in universe")

    stmt = (
        select(FeatureMatrix)
        .where(
            FeatureMatrix.ticker_id.in_(ticker_ids),
            FeatureMatrix.feature_schema_version == "v1.0",
        )
        .order_by(FeatureMatrix.ticker_id, FeatureMatrix.bar_date)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    if not rows:
        raise ValueError("No feature_matrix rows found for universe tickers")

    df_records: list[dict] = []
    for row in rows:
        rec = {"ticker_id": row.ticker_id, "bar_date": row.bar_date}
        for col in FEATURE_COLUMNS:
            rec[col] = _to_float(getattr(row, col, 0.0))
        for col in TARGET_COLUMNS:
            rec[col] = _to_float(getattr(row, col, None))
        df_records.append(rec)
    rows_df = pd.DataFrame(df_records)

    groups: dict[uuid.UUID, list] = {}
    for row in rows:
        groups.setdefault(row.ticker_id, []).append(row)

    all_features: list[np.ndarray] = []
    all_targets: list[np.ndarray] = []
    all_dates: list[date] = []

    for ticker_id, ticker_rows in groups.items():
        if len(ticker_rows) <= SEQUENCE_LENGTH:
            continue

        features_arr = np.array(
            [_row_to_feature_vector(r) for r in ticker_rows], dtype=np.float32
        )
        targets_arr = np.array(
            [_row_to_target_vector(r) for r in ticker_rows], dtype=np.float32
        )
        ticker_dates = [r.bar_date for r in ticker_rows]

        feature_mean = features_arr.mean(axis=0)
        feature_std = features_arr.std(axis=0)
        feature_std[feature_std < 1e-8] = 1.0
        features_arr = (features_arr - feature_mean) / feature_std

        for i in range(SEQUENCE_LENGTH - 1, len(ticker_rows)):
            win_start = i - SEQUENCE_LENGTH + 1
            win_end = i + 1
            all_features.append(features_arr[win_start:win_end])
            all_targets.append(targets_arr[i])
            all_dates.append(ticker_dates[i])

    if not all_features:
        raise ValueError(f"No windows built: need >{SEQUENCE_LENGTH} rows per ticker")

    X = np.stack(all_features, axis=0)
    y = np.stack(all_targets, axis=0)
    return X, y, all_dates, rows_df


def _snapshot_feature_distribution(
    features: np.ndarray, feature_names: list[str]
) -> dict:
    """Compute per-feature histogram summaries for drift comparison.

    Each feature gets a 10-bin histogram, bin edges, mean, and std.
    The distribution is stored in training_runs.model_metadata for
    the S6 feature-drift KL signal.
    """
    dist: dict = {}
    for i, name in enumerate(feature_names):
        col = features[:, i]
        valid = col[~np.isnan(col)]
        if len(valid) < 10:
            dist[name] = {"hist": [], "bin_edges": [], "mean": 0.0, "std": 0.0}
            continue
        hist, bin_edges = np.histogram(valid, bins=10)
        dist[name] = {
            "hist": hist.tolist(),
            "bin_edges": [float(e) for e in bin_edges],
            "mean": float(np.nanmean(col)),
            "std": float(np.nanstd(col)),
        }
    return dist


async def train_universe(
    universe_id: uuid.UUID,
    as_of_date: date,
    db_session: AsyncSession,
    artifact_store: ArtifactStore,
    hyperparams: dict | None = None,
) -> TrainingResult:
    hparams = {**DEFAULT_HYPERPARAMS, **(hyperparams or {})}

    session = db_session
    training_run_id: uuid.UUID | None = None
    artifact_ids: list[uuid.UUID] = []
    per_epoch_losses: list[dict] = []

    try:
        ticker_ids = await _fetch_active_ticker_ids(session, universe_id)
        universe_name = await _fetch_universe_name(session, universe_id)
        slug = _universe_slug(universe_name)

        X, y, all_dates, features_df = await _build_training_data(session, ticker_ids)
        num_tickers = len(ticker_ids)
        num_samples = X.shape[0]

        train_dates, cal_dates, val_dates = create_walk_forward_split(all_dates)

        train_mask = np.array([d in set(train_dates) for d in all_dates])
        cal_mask = np.array([d in set(cal_dates) for d in all_dates])
        val_mask = np.array([d in set(val_dates) for d in all_dates])

        window_bounds = {
            "train_window_start": min(train_dates) if train_dates else None,
            "train_window_end": max(train_dates) if train_dates else None,
            "calibration_window_start": min(cal_dates) if cal_dates else None,
            "calibration_window_end": max(cal_dates) if cal_dates else None,
            "validation_window_start": min(val_dates) if val_dates else None,
            "validation_window_end": max(val_dates) if val_dates else None,
        }

        training_run = await ml_repo.create_training_run(
            session,
            universe_id=universe_id,
            triggered_by="weekly_scheduled",
            window_bounds=window_bounds,
        )
        training_run.hyperparams_snapshot = hparams
        training_run_id = training_run.id

        artifact_service = ArtifactLifecycleService(artifact_store)

        # ── LSTM training ────────────────────────────────────────────────
        X_train = torch.from_numpy(X[train_mask])
        y_train = torch.from_numpy(y[train_mask])
        X_val = torch.from_numpy(X[val_mask])
        y_val = torch.from_numpy(y[val_mask])

        train_ds = TensorDataset(X_train, y_train)
        val_ds = TensorDataset(X_val, y_val)

        train_loader = DataLoader(
            train_ds, batch_size=hparams["batch_size"], shuffle=False
        )
        val_loader = DataLoader(val_ds, batch_size=hparams["batch_size"], shuffle=False)

        lstm_engine = LSTMMathEngine()
        lstm_trainer = LSTMTrainer(
            lstm_engine,
            max_epochs=hparams["max_epochs"],
            batch_size=hparams["batch_size"],
            patience=hparams["patience"],
            lr_patience=hparams["lr_patience"],
            lr_factor=hparams["lr_factor"],
            lr=hparams["lr"],
            weight_decay=hparams["weight_decay"],
        )

        lstm_history = lstm_trainer.train_model(train_loader, val_loader)
        per_epoch_losses.append(
            {
                "model_role": "lstm",
                "train_loss": lstm_history["train_loss"],
                "val_loss": lstm_history["val_loss"],
                "epochs_run": lstm_history["epochs_run"],
            }
        )

        lstm_bytes = lstm_engine.serialize()
        lstm_artifact = await artifact_service.save_artifact(
            session,
            universe_id=universe_id,
            universe_slug=slug,
            model_role="lstm",
            training_run_id=training_run_id,
            data=lstm_bytes,
        )
        artifact_ids.append(lstm_artifact.id)

        # ── TFT Quad-Array training ───────────────────────────────────────
        tft_hparams = {
            "hidden_size": 64,
            "attention_head_size": 4,
            "dropout": 0.1,
            "hidden_continuous_size": 32,
            "learning_rate": hparams["lr"],
            "max_epochs": hparams.get("tft_max_epochs", 50),
            "patience": 4,
        }

        tft_horizon_map: list[tuple[str, str, str]] = [
            ("t1", "target_t1", "tft_t1"),
            ("t5", "target_t5", "tft_t5"),
            ("t10", "target_t10", "tft_t10"),
            ("t15", "target_t15", "tft_t15"),
        ]

        train_dates_set = set(train_dates)
        val_dates_set = set(val_dates)
        tft_train_df = features_df[features_df["bar_date"].isin(train_dates_set)]
        tft_val_df = features_df[features_df["bar_date"].isin(val_dates_set)]

        tft_datasets: dict[str, object] = {}
        tft_loaders: dict[str, DataLoader] = {}
        tft_val_loaders: dict[str, DataLoader] = {}

        for horizon, target_col, _role in tft_horizon_map:
            try:
                train_ds = build_tft_dataset(
                    tft_train_df,
                    target_column=target_col,
                )
                val_ds = build_tft_dataset(
                    tft_val_df,
                    target_column=target_col,
                )
                tft_datasets[horizon] = train_ds
                tft_loaders[horizon] = train_ds.to_dataloader(
                    train=True, batch_size=hparams["batch_size"]
                )
                tft_val_loaders[horizon] = val_ds.to_dataloader(
                    train=False, batch_size=hparams["batch_size"]
                )
                logger.info(
                    "Built TFT dataset for horizon=%s: %d train samples, %d val samples",
                    horizon,
                    len(train_ds),
                    len(val_ds),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to build TFT dataset for horizon=%s: %s", horizon, exc
                )

        if tft_datasets:
            try:
                set_seed(42)
                quad_array = TemporalFusionQuadArray(datasets=tft_datasets)

                with tempfile.TemporaryDirectory() as tmpdir:
                    tft_results = quad_array.train_model(
                        train_loaders=tft_loaders,
                        val_loaders=tft_val_loaders,
                        max_epochs=tft_hparams["max_epochs"],
                        patience=tft_hparams["patience"],
                        enable_progress_bar=False,
                    )

                    for horizon, _target_col, model_role in tft_horizon_map:
                        if horizon not in quad_array.models:
                            logger.warning(
                                "TFT model for horizon=%s not initialized; skipping artifact save.",
                                horizon,
                            )
                            continue
                        try:
                            tft_model = quad_array.models[horizon]
                            tft_model.eval()
                            model_path = Path(tmpdir) / f"{model_role}.pt"
                            torch.save(tft_model.state_dict(), model_path)
                            model_bytes = model_path.read_bytes()
                            tft_bytes = pickle.dumps(
                                {
                                    "state_dict_bytes": model_bytes,
                                    "hidden_size": tft_hparams["hidden_size"],
                                    "attention_head_size": tft_hparams[
                                        "attention_head_size"
                                    ],
                                    "dropout": tft_hparams["dropout"],
                                    "hidden_continuous_size": tft_hparams[
                                        "hidden_continuous_size"
                                    ],
                                    "learning_rate": tft_hparams["learning_rate"],
                                }
                            )
                            tft_artifact = await artifact_service.save_artifact(
                                session,
                                universe_id=universe_id,
                                universe_slug=slug,
                                model_role=model_role,
                                training_run_id=training_run_id,
                                data=tft_bytes,
                            )
                            artifact_ids.append(tft_artifact.id)
                            logger.info("Saved TFT artifact for role=%s", model_role)
                        except Exception as exc:
                            logger.exception(
                                "Failed to save TFT artifact for role=%s: %s",
                                model_role,
                                exc,
                            )

                    for horizon, _target_col, model_role in tft_horizon_map:
                        if horizon in tft_results:
                            per_epoch_losses.append(
                                {
                                    "model_role": model_role,
                                    "best_val_loss": tft_results[horizon].get(
                                        "best_val_loss"
                                    ),
                                    "stopped_epoch": tft_results[horizon].get(
                                        "stopped_epoch"
                                    ),
                                }
                            )
            except Exception as tft_exc:
                logger.exception(
                    "TFT training failed for universe '%s': %s",
                    slug,
                    tft_exc,
                )
                raise
        else:
            logger.warning("No TFT datasets built; skipping TFT training entirely.")

        # ── Conformal calibrator ─────────────────────────────────────────
        cal_train_indices = np.where(train_mask)[0]
        cal_indices = np.where(cal_mask)[0]

        X_cal = torch.from_numpy(X[cal_mask])
        X_features = X[:, -1, :]

        lstm_engine.eval()
        with torch.no_grad():
            lstm_cal_preds = lstm_engine(X_cal).cpu().numpy()

        y_cal_all_preds = np.zeros_like(y)
        y_cal_all_preds[cal_mask] = lstm_cal_preds
        y_cal_all_preds[train_mask] = y[train_mask]

        calibrator = ConformalCalibrator(alpha=hparams["alpha"])
        calibrator.fit(y, y_cal_all_preds, X_features, cal_indices, cal_train_indices)

        w_max = calibrator.compute_W_max(X_features[cal_mask])

        cal_buf = BytesIO()
        torch.save(
            {
                "quantiles": calibrator.quantiles,
                "alpha": calibrator.alpha,
                "residual_predictor_state": calibrator.residual_predictor.state_dict(),
                "w_max": w_max,
            },
            cal_buf,
        )
        cal_bytes = cal_buf.getvalue()
        cal_artifact = await artifact_service.save_artifact(
            session,
            universe_id=universe_id,
            universe_slug=slug,
            model_role="conformal",
            training_run_id=training_run_id,
            data=cal_bytes,
        )
        cal_artifact.model_metadata = {"w_max": w_max}
        artifact_ids.append(cal_artifact.id)

        # ── Validation ───────────────────────────────────────────────────
        lstm_engine.eval()
        with torch.no_grad():
            val_preds = lstm_engine(X_val).cpu().numpy()
        val_true = y_val.cpu().numpy()

        val_loss_per_horizon = {}
        for h in range(N_TARGETS):
            mse = float(np.mean((val_preds[:, h] - val_true[:, h]) ** 2))
            mae = float(np.mean(np.abs(val_preds[:, h] - val_true[:, h])))
            val_loss_per_horizon[TARGET_COLUMNS[h]] = {"mse": mse, "mae": mae}

        validation_metrics = {
            "horizon_metrics": val_loss_per_horizon,
            "overall_mse": float(np.mean((val_preds - val_true) ** 2)),
            "best_val_loss": lstm_history.get("best_val_loss"),
            "num_tickers": num_tickers,
            "num_train_samples": int(train_mask.sum()),
            "num_calibration_samples": int(cal_mask.sum()),
            "num_validation_samples": int(val_mask.sum()),
        }

        feature_distribution = _snapshot_feature_distribution(
            X[train_mask, -1, :], FEATURE_COLUMNS
        )

        await ml_repo.complete_training_run(
            session,
            run_id=training_run_id,
            status="completed",
            validation_metrics=validation_metrics,
            num_tickers=num_tickers,
            num_training_samples=num_samples,
            model_metadata={"feature_distribution": feature_distribution},
        )

        await session.flush()

        return TrainingResult(
            training_run_id=training_run_id,
            artifact_ids=artifact_ids,
            validation_metrics=validation_metrics,
            per_epoch_losses=per_epoch_losses,
            status="completed",
        )

    except Exception as exc:
        logger.exception("Training failed for universe %s: %s", universe_id, exc)
        if training_run_id is not None:
            try:
                await ml_repo.complete_training_run(
                    session,
                    run_id=training_run_id,
                    status="failed",
                    error_summary=str(exc)[:500],
                )
                await session.flush()
            except Exception as inner:
                logger.exception("Failed to record training failure: %s", inner)

        return TrainingResult(
            training_run_id=training_run_id or uuid.UUID(int=0),
            artifact_ids=artifact_ids,
            validation_metrics={},
            per_epoch_losses=per_epoch_losses,
            status="failed",
            error=str(exc)[:500],
        )
