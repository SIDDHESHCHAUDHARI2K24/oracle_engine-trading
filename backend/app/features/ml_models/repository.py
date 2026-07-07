import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ml_models.models import (
    InferenceRun,
    ModelArtifact,
    Prediction,
    TrainingRun,
)


async def create_training_run(
    session: AsyncSession,
    universe_id: uuid.UUID,
    triggered_by: str,
    window_bounds: dict | None = None,
) -> TrainingRun:
    kwargs: dict = {}
    if window_bounds:
        kwargs.update(window_bounds)
    run = TrainingRun(
        universe_id=universe_id,
        triggered_by=triggered_by,
        status="running",
        **kwargs,
    )
    session.add(run)
    await session.flush()
    return run


async def complete_training_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    status: str,
    validation_metrics: dict | None = None,
    num_tickers: int | None = None,
    num_training_samples: int | None = None,
    error_summary: str | None = None,
    model_metadata: dict | None = None,
) -> TrainingRun:
    run = await session.get(TrainingRun, run_id)
    if run is None:
        raise ValueError(f"TrainingRun {run_id} not found")
    run.status = status
    run.completed_at = datetime.now(timezone.utc)
    if validation_metrics is not None:
        run.validation_metrics = validation_metrics
    if num_tickers is not None:
        run.num_tickers = num_tickers
    if num_training_samples is not None:
        run.num_training_samples = num_training_samples
    if error_summary is not None:
        run.error_summary = error_summary
    if model_metadata is not None:
        run.model_metadata = model_metadata
    await session.flush()
    return run


async def get_training_run(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> TrainingRun | None:
    return await session.get(TrainingRun, run_id)


async def get_training_history(
    session: AsyncSession,
    universe_id: uuid.UUID,
    limit: int = 50,
) -> list[TrainingRun]:
    result = await session.execute(
        select(TrainingRun)
        .where(TrainingRun.universe_id == universe_id)
        .order_by(TrainingRun.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_training_run(
    session: AsyncSession,
    universe_id: uuid.UUID,
) -> TrainingRun | None:
    result = await session.execute(
        select(TrainingRun)
        .where(TrainingRun.universe_id == universe_id)
        .order_by(TrainingRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_artifacts_for_universe(
    session: AsyncSession,
    universe_id: uuid.UUID,
) -> list[ModelArtifact]:
    result = await session.execute(
        select(ModelArtifact)
        .where(ModelArtifact.universe_id == universe_id)
        .order_by(ModelArtifact.created_at.desc())
    )
    return list(result.scalars().all())


async def create_inference_run(
    session: AsyncSession,
    universe_id: uuid.UUID,
    triggered_by: str,
    inference_date: date,
    artifact_ids: list[uuid.UUID],
) -> InferenceRun:
    run = InferenceRun(
        universe_id=universe_id,
        triggered_by=triggered_by,
        inference_date=inference_date,
        artifact_ids=[str(a) for a in artifact_ids],
        status="running",
    )
    session.add(run)
    await session.flush()
    return run


async def get_inference_run(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> InferenceRun | None:
    return await session.get(InferenceRun, run_id)


async def complete_inference_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    status: str,
    num_tickers_scored: int | None = None,
    error_summary: str | None = None,
) -> InferenceRun:
    run = await session.get(InferenceRun, run_id)
    if run is None:
        raise ValueError(f"InferenceRun {run_id} not found")
    run.status = status
    run.completed_at = datetime.now(timezone.utc)
    if num_tickers_scored is not None:
        run.num_tickers_scored = num_tickers_scored
    if error_summary is not None:
        run.error_summary = error_summary
    await session.flush()
    return run


async def upsert_predictions(
    session: AsyncSession,
    predictions: list[dict],
) -> int:
    inserted = 0
    for p in predictions:
        existing = await session.execute(
            select(Prediction).where(
                Prediction.ticker_id == p["ticker_id"],
                Prediction.universe_id == p["universe_id"],
                Prediction.inference_date == p["inference_date"],
            )
        )
        existing = existing.scalar_one_or_none()  # type: ignore[assignment]
        if existing is not None:
            for col in (
                "pred_t1",
                "pred_lo_t1",
                "pred_hi_t1",
                "conviction_t1",
                "pred_t5",
                "pred_lo_t5",
                "pred_hi_t5",
                "conviction_t5",
                "pred_t10",
                "pred_lo_t10",
                "pred_hi_t10",
                "conviction_t10",
                "pred_t15",
                "pred_lo_t15",
                "pred_hi_t15",
                "conviction_t15",
                "lstm_outputs",
                "tft_q10",
                "tft_q50",
                "tft_q90",
            ):
                setattr(existing, col, p[col])
        else:
            pred = Prediction(**p)
            session.add(pred)
            inserted += 1
    await session.flush()
    return inserted


async def get_predictions_for_date(
    session: AsyncSession,
    universe_id: uuid.UUID,
    inference_date: date,
) -> list[Prediction]:
    result = await session.execute(
        select(Prediction).where(
            Prediction.universe_id == universe_id,
            Prediction.inference_date == inference_date,
        )
    )
    return list(result.scalars().all())
