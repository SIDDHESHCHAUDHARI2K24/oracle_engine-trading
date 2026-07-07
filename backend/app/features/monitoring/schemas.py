import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CoverageMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    universe_id: uuid.UUID
    horizon: str
    measurement_date: date
    window_size: int
    realized_coverage: float | None = None
    nominal_coverage: float
    num_tickets_resolved: int | None = None
    is_alert: bool
    computed_at: datetime


class CoverageMetricsQuery(BaseModel):
    universe_id: uuid.UUID
    horizon: str = "T5"
    window_size: int = 30
    limit: int = 90


class FeatureDriftMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    universe_id: uuid.UUID
    feature_name: str
    measurement_date: date
    kl_divergence: float | None = None
    threshold_breached: bool
    training_run_id: uuid.UUID | None = None
    computed_at: datetime


class SystemAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    severity: str
    code: str
    universe_id: uuid.UUID | None = None
    message: str
    context: dict
    created_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


class AlertAcknowledgeRequest(BaseModel):
    pass


class AlertResolveRequest(BaseModel):
    pass


class AlertActionResponse(BaseModel):
    message: str
    alert: SystemAlertResponse


class ModelHealthSummary(BaseModel):
    universe_id: uuid.UUID
    universe_name: str
    last_retrain_at: datetime | None = None
    open_alert_count: int
    alert_severity: str | None = None
    data_freshness_hours: float | None = None
    conviction_correlation: float | None = None
    coverage_30d: float | None = None


class ModelCardDetail(BaseModel):
    universe_id: uuid.UUID
    universe_name: str
    last_retrain_at: datetime | None = None
    open_alert_count: int
    alert_severity: str | None = None
    data_freshness_hours: float | None = None
    training_history: list[dict]
    active_artifacts: list[dict]
    validation_metrics: dict | None = None
    coverage_30d: dict[str, float | None] = {}
    coverage_90d: dict[str, float | None] = {}
    recent_tickets: list[dict]
