from datetime import datetime, timedelta, timezone

import pytest

from app.features.data_ingestion.models import IngestRun
from app.features.monitoring.signals.freshness import (
    compute_freshness,
    compute_pipeline_success,
)


class _FakeAlertService:
    def __init__(self):
        self.alerts = []

    async def raise_alert(self, session, severity, code, message, universe_id=None, context=None):
        self.alerts.append({
            "severity": severity,
            "code": code,
            "message": message,
            "universe_id": universe_id,
            "context": context,
        })


@pytest.mark.asyncio
async def test_freshness_stale_raises_critical(db_session):
    stale_time = datetime.now(timezone.utc) - timedelta(hours=40)
    ingest = IngestRun(
        triggered_by="test",
        triggered_at=stale_time,
        completed_at=stale_time,
        status="succeeded",
        ohlcv_rows_inserted=100,
        macro_rows_inserted=10,
    )
    db_session.add(ingest)
    await db_session.flush()

    alert_service = _FakeAlertService()
    result = await compute_freshness(db_session, alert_service=alert_service)

    assert result is not None
    assert result["stale"] is True
    crits = [a for a in alert_service.alerts if a["severity"] == "critical"]
    assert len(crits) >= 1
    assert crits[0]["code"] == "INGEST_STALE"


@pytest.mark.asyncio
async def test_freshness_recent_no_alert(db_session):
    recent_time = datetime.now(timezone.utc) - timedelta(hours=2)
    ingest = IngestRun(
        triggered_by="test",
        triggered_at=recent_time,
        completed_at=recent_time,
        status="succeeded",
        ohlcv_rows_inserted=100,
        macro_rows_inserted=10,
    )
    db_session.add(ingest)
    await db_session.flush()

    alert_service = _FakeAlertService()
    result = await compute_freshness(db_session, alert_service=alert_service)

    assert result is not None
    assert result["stale"] is False
    assert len(alert_service.alerts) == 0


@pytest.mark.asyncio
async def test_pipeline_success_below_threshold(monkeypatch):
    async def mock_get_recent_runs(limit=100, deployment_name=None):
        now = datetime.now(timezone.utc)
        runs = []
        for i in range(10):
            state = "COMPLETED" if i < 9 else "FAILED"
            runs.append({
                "id": f"run-{i}",
                "name": f"flow-{i}",
                "state": state,
                "start_time": (now - timedelta(hours=1)).isoformat(),
                "end_time": now.isoformat(),
            })
        return runs

    monkeypatch.setattr(
        "app.features.monitoring.signals.freshness.get_recent_runs",
        mock_get_recent_runs,
    )

    alert_service = _FakeAlertService()
    result = await compute_pipeline_success(alert_service=alert_service, lookback_hours=24)

    assert result is not None
    assert result["success_rate"] == 0.9
    assert result["trigger_alert"] is True

    warnings = [a for a in alert_service.alerts if a["severity"] == "warning"]
    assert len(warnings) >= 1
    assert warnings[0]["code"] == "PIPELINE_SUCCESS_LOW"


@pytest.mark.asyncio
async def test_pipeline_success_healthy(monkeypatch):
    async def mock_get_recent_runs(limit=100, deployment_name=None):
        now = datetime.now(timezone.utc)
        runs = []
        for i in range(50):
            state = "FAILED" if i < 1 else "COMPLETED"
            runs.append({
                "id": f"run-{i}",
                "name": f"flow-{i}",
                "state": state,
                "start_time": (now - timedelta(hours=1)).isoformat(),
                "end_time": now.isoformat(),
            })
        return runs

    monkeypatch.setattr(
        "app.features.monitoring.signals.freshness.get_recent_runs",
        mock_get_recent_runs,
    )

    alert_service = _FakeAlertService()
    result = await compute_pipeline_success(alert_service=alert_service, lookback_hours=24)

    assert result is not None
    assert result["success_rate"] == 0.98
    assert result["trigger_alert"] is False
    assert len(alert_service.alerts) == 0
