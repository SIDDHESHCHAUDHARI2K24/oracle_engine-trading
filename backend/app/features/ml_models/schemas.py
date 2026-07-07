from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TrainingRunBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    universe_id: str
    triggered_by: str
    train_window_start: date | None = None
    train_window_end: date | None = None
    calibration_window_start: date | None = None
    calibration_window_end: date | None = None
    validation_window_start: date | None = None
    validation_window_end: date | None = None
    num_tickers: int | None = None
    num_training_samples: int | None = None
    hyperparams_snapshot: dict | None = None
    validation_metrics: dict | None = None


class TrainingRunResponse(TrainingRunBase):
    id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    error_summary: str | None = None


class ModelArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    universe_id: str
    training_run_id: str
    model_role: str
    artifact_path: str
    size_bytes: int | None = None
    is_active: bool
    metadata: dict
    created_at: datetime
    archived_at: datetime | None = None


class InferenceRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    universe_id: str
    triggered_by: str
    inference_date: date
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    artifact_ids: list
    num_tickers_scored: int | None = None
    error_summary: str | None = None


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inference_run_id: str
    ticker_id: str
    universe_id: str
    inference_date: date
    pred_t1: float
    pred_lo_t1: float
    pred_hi_t1: float
    conviction_t1: float
    pred_t5: float
    pred_lo_t5: float
    pred_hi_t5: float
    conviction_t5: float
    pred_t10: float
    pred_lo_t10: float
    pred_hi_t10: float
    conviction_t10: float
    pred_t15: float
    pred_lo_t15: float
    pred_hi_t15: float
    conviction_t15: float
    lstm_outputs: list[float]
    tft_q10: list[float]
    tft_q50: list[float]
    tft_q90: list[float]
    created_at: datetime


class TrainingHistoryResponse(BaseModel):
    universe_id: str
    runs: list[TrainingRunResponse]


class ArtifactListResponse(BaseModel):
    universe_id: str
    artifacts: list[ModelArtifactResponse]


class RollbackRequest(BaseModel):
    artifact_id: str


class TriggerRetrainResponse(BaseModel):
    message: str
    deployment_id: str | None = None


class TriggerInferenceResponse(BaseModel):
    message: str
    deployment_id: str | None = None
