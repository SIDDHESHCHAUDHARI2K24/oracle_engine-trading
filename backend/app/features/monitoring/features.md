# Feature 8 — Monitoring & Model Health

Developer documentation for the monitoring feature.

---

## Architecture Overview

The monitoring feature implements 7 observability signals, an alert system with severity-based
routing, and a Slack notifier for critical alerts. It provides the data layer for the Model Health
Dashboard and the internal alerting backbone used by every other feature.

```
                      ┌──────────────────────────────┐
                      │     Model Health Dashboard    │
                      │  /health, /coverage, /drift   │
                      └──────────────┬───────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
     ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
     │  Signal Layer   │  │  Alert System   │  │  Slack Notifier     │
     │  (7 signals)    │  │  (AlertService) │  │  (core/notifier.py) │
     └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘
              │                    │                       │
              ▼                    ▼                       ▼
     ┌───────────────────────────────────────────────────────────┐
     │                    Repository Layer                       │
     │  coverage_metrics | feature_drift_metrics | system_alerts │
     └───────────────────────────────────────────────────────────┘
```

### Signal Layer

Each signal is a self-contained module under `signals/`. Every signal:
- Queries its relevant domain tables (e.g., `ConvictionTicket` for coverage, `FeatureMatrix` for drift)
- Computes a metric
- Persists the metric via the monitoring repository
- Raises an alert via `AlertService` if thresholds are breached

### Alert System

`AlertService` (in `service.py`):
- `raise_alert()` — deduplicates by `(code, universe_id)` to avoid alert storms; reuses existing
  open alert, updating its context
- If severity is `critical`, fires a Slack notification (no-op if `SLACK_WEBHOOK_URL` is unset)
- `acknowledge_alert()` / `resolve_alert()` — lifecycle management
- `list_open_alerts()` — filtered by severity and universe

### Slack Notifier

`app/core/services/notifier.py` — thin wrapper around `slack_sdk`. Sends a formatted message with
alert code, severity, message, and a link to the Prefect UI. No-op if webhook URL is not
configured.

---

## File Map

```
backend/app/features/monitoring/
├── __init__.py
├── models.py              # CoverageMetric, FeatureDriftMetric, SystemAlert
├── schemas.py             # Pydantic response/request schemas
├── repository.py          # DB access: upsert, list, CRUD
├── service.py             # AlertService — raise/acknowledge/resolve/list alerts
├── dependencies.py        # Shared DI (re-exports get_async_session)
├── router.py              # APIRouter mounting the endpoints sub-router
├── features.md            # This file
├── endpoints/
│   ├── __init__.py
│   └── monitoring.py      # REST endpoints: /health, /coverage, /drift, /alerts
├── signals/
│   ├── __init__.py
│   ├── coverage.py        # Conformal coverage signal + COVERAGE_BREACH alert
│   ├── drift.py           # KL divergence feature drift + FEATURE_DRIFT alert
│   ├── correlation.py     # Spearman conviction-vs-outcome + CONVICTION_UNPREDICTIVE alert
│   ├── loss_curve.py      # Train/val divergence detection + OVERFITTING_DETECTED alert
│   ├── freshness.py       # Ingest staleness + INGEST_STALE, pipeline success + PIPELINE_SUCCESS_LOW
│   └── backtest_drift.py  # Pass-rate trend + BACKTEST_DRIFT alert
├── signals/tests/
│   ├── __init__.py
│   └── test_drift.py
└── tests/
    ├── __init__.py
    ├── test_coverage.py
    ├── test_correlation.py
    ├── test_freshness.py
    └── test_loss_curve.py
```

The signal files are co-located with their tests. The orchestration layer that invokes these signals
lives in `backend/app/orchestration/flows/daily_monitoring.py`.

---

## Signal Descriptions and Alert Codes

### 1. Coverage Signal (`signals/coverage.py`)
- **Class**: `CoverageSignal`
- **What**: Computes realized vs. nominal conformal coverage on resolved conviction tickets
- **How**: For each `(universe, horizon, window_size)` tuple, counts tickets where `actual_return`
  falls within `[conformal_lower, conformal_upper]`. Requires ≥5 resolved tickets to emit a metric.
- **Threshold**: Realized coverage < 80%
- **Sustained check**: Must be below threshold for 5 consecutive measurements before alerting
- **Alert code**: `COVERAGE_BREACH`
- **Orchestration**: `conformal_coverage_check` flow (daily 11pm ET)

### 2. Feature Drift Signal (`signals/drift.py`)
- **Class**: `FeatureDriftSignal`
- **What**: Computes per-feature KL divergence between current 252-day distribution and the training
  distribution snapshot stored in `training_runs.model_metadata["feature_distribution"]`
- **How**: Bins both distributions using training histogram bin edges, computes `scipy.stats.entropy`
- **Threshold**: KL divergence > 0.3 per feature
- **Alert code**: `FEATURE_DRIFT`
- **Orchestration**: `daily_monitoring` flow (Mon/Thu only)

### 3. Correlation Signal (`signals/correlation.py`)
- **Function**: `compute_conviction_correlation()`
- **What**: Spearman rank correlation between `conviction_score` and `actual_return` on resolved
  tickets in a 90-day rolling window
- **How**: `scipy.stats.spearmanr(scores, returns)`
- **Threshold**: Correlation < 0.2
- **Sustained check**: Must be below threshold for 3 consecutive measurements before escalating to
  `warning`
- **Alert code**: `CONVICTION_UNPREDICTIVE`
- **Orchestration**: `daily_monitoring` flow (Mon/Thu only)

### 4. Loss Curve Signal (`signals/loss_curve.py`)
- **Class**: `LossCurveSignal`
- **What**: Detects overfitting by checking whether train loss is falling while validation loss is
  rising over the last 5 epochs
- **How**: `detect_overfitting()` compares `recent_train[-1] < recent_train[0]` and
  `recent_val[-1] > recent_val[0]`
- **Alert code**: `OVERFITTING_DETECTED`
- **Note**: Called after each retrain, not on a schedule. Results are stored in
  `training_runs.model_metadata["signal_loss_curve"]`

### 5. Freshness Signal (`signals/freshness.py`)
- **Function**: `compute_freshness()`
- **What**: Time since last successful `IngestRun`
- **Threshold**: > 36 hours
- **Alert code**: `INGEST_STALE`
- **Orchestration**: `daily_monitoring` flow (daily 10pm ET)

### 6. Pipeline Success Signal (`signals/freshness.py`)
- **Function**: `compute_pipeline_success()`
- **What**: Success rate of Prefect flow runs over the past 7 days
- **How**: Queries Prefect API via `core/services/prefect_client.py` for recent runs, counts
  `COMPLETED` vs total
- **Threshold**: Success rate < 95%
- **Alert code**: `PIPELINE_SUCCESS_LOW`
- **Orchestration**: `daily_monitoring` flow (daily 10pm ET)

### 7. Backtest Drift Signal (`signals/backtest_drift.py`)
- **Function**: `compute_backtest_drift()`
- **What**: Pass-rate change between the two most recent backtest runs
- **How**: Computes fraction of tickers passing ≥2 strategies per run, compares deltas
- **Threshold**: >5 percentage point drop (`warning`), >10pp drop (escalates)
- **Alert code**: `BACKTEST_DRIFT`
- **Orchestration**: `daily_monitoring` flow (Mon/Thu only)

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/monitoring/health` | List model health summaries for all universes |
| `GET` | `/api/v1/monitoring/health/{universe_id}` | Per-universe model card with history and artifacts |
| `GET` | `/api/v1/monitoring/coverage` | Coverage metrics (query params: `universe_id`, `horizon`, `window_size`) |
| `GET` | `/api/v1/monitoring/drift` | Feature drift metrics (query params: `universe_id`, `measurement_date`) |
| `GET` | `/api/v1/monitoring/alerts` | List open alerts (optional filters: `severity`, `universe_id`) |
| `POST` | `/api/v1/monitoring/alerts/{alert_id}/acknowledge` | Acknowledge an alert |
| `POST` | `/api/v1/monitoring/alerts/{alert_id}/resolve` | Resolve an alert |

---

## How to Add a New Monitoring Signal

1. **Create the signal file** at `signals/<name>.py`:
   - Implement the computation logic
   - Call `monitoring_repo.upsert_*()` to persist the result
   - Call `alert_service.raise_alert()` if a threshold is breached

2. **Add the model** (if new metric type) in `models.py`:
   - New SQLAlchemy model class with appropriate columns and constraints
   - Run `alembic revision --autogenerate -m "add <metric> table"`

3. **Add the schema** in `schemas.py` if the metric is exposed via API

4. **Add repository functions** in `repository.py` for CRUD on the new metric

5. **Wire into an orchestration flow** in `backend/app/orchestration/flows/daily_monitoring.py`:
   - Create a `@task` wrapper
   - Add to the flow body (conditionally if it's a heavy computation)

6. **Add the alert code** to the [Alert Response Runbook](../../../../docs/runbooks/alert-response.md)

7. **Write tests** in `tests/test_<name>.py`

---

## Testing Approach

Tests use `pytest` + `pytest-asyncio` with `AsyncMock` for database sessions. Each signal has its
own test file:

| Test File | What It Covers |
|---|---|
| `test_coverage.py` | CoverageSignal with mock resolved tickets, threshold boundary tests |
| `test_correlation.py` | Spearman correlation with known score/return pairs, edge cases (<20 rows) |
| `test_freshness.py` | Freshness with mock IngestRun, pipeline success with mock Prefect data |
| `test_loss_curve.py` | Overfitting detection with synthetic train/val loss curves |
| `signals/tests/test_drift.py` | KL divergence computation, threshold boundary |

Test strategy:
- **Unit tests**: Signal logic with mocked DB — verifies thresholds, alert raising, sustained checks
- **Integration tests**: Signal against real test DB with seeded data (requires Postgres)
- **No live API tests** in monitoring — all external calls (Prefect API, Slack) are mocked
