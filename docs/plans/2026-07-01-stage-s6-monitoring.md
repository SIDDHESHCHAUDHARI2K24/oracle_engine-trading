# Stage S6 — Monitoring & Polish — Detailed Implementation Plan

> **Date**: 2026-07-01
> **Status**: Ready for execution. Brainstorming complete; 5 decisions locked.
> **Source**: `features-to-develop/development-plan-S6.md`, `docs/mbi-pipeline-a-v1-design.md` §9-§11
> **Previous**: S5 — Backtesting + Conviction Tickets (60 tests, green)
> **Next**: Pipeline B (v1 complete)
> **Approach**: Subagent-driven parallel (4 streams, ~6-8 agent-days)

---

## Decisions Locked During Brainstorming

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | TFT fix first (P6.T0), then full monitoring | Monitoring needs ensemble signals; degraded LSTM-only gives partial picture |
| D2 | Feature distribution snapshotted at train time | Stored in `training_runs.model_metadata`; most correct, backward-compat null-safe |
| D3 | Alembic merge migration before S6 monitoring tables | Both heads valid (S1+S5); merge is cleanest path |
| D4 | Frontend routes nest under `/monitoring` | Extends existing `MonitoringPage`; avoids duplicate nav entries |
| D5 | Load-sanity: simple pytest async script | No new dependencies; documents findings inline; validates pool sizing |

---

## Dependency Map

```
P6.T0 (TFT fix + distribution snapshot)
  │
  ▼
P6.T1 (Schema + Alert Service) ──┬──→ P6.T2 (Coverage + Loss) ──┐
                                  ├──→ P6.T3 (Corr + Fresh + Pipe)─┤
                                  ├──→ P6.T4 (KL Drift) ──────────┤
                                  │                                 ▼
                                  ├──→ P6.T6 (Housekeeping) ──→ P6.T5 (Flows + Wiring)
                                  │                                      │
                                  │                                      ▼
                                  └──→ P6.T7 (Dashboard UI) ──→ P6.T8 (Alerts UI)
                                                                         │
                                                                         ▼
                                                                  P6.T9 (E2E + Perf)
                                                                         │
                                                                         ▼
                                                                  P6.T10 (Autonomy + Docs)
```

**Parallel streams after T1**:
| Stream | Tasks | Agent |
|--------|-------|-------|
| A (Signals) | T2 + T3 + T4 → T5 | Backend agent(s) |
| B (Housekeeping) | T6 | Backend agent (independent) |
| C (Frontend) | T7 → T8 | Frontend agent |

---

## P6.T0: Pre-Requisite Fixes (TFT + Training Distribution)

**Effort**: M / 1.5 days | **Dependencies**: None (starts from S5) | **Risk**: Medium

### P6.T0.S1: Fix TFT Training Compatibility

**Files to modify**:
- `backend/pyproject.toml` — pin `torchmetrics<1.0` or upgrade `pytorch-forecasting`
- `backend/app/features/ml_models/service.py` — remove try/except TFT degradation wrapper
- `backend/app/features/ml_models/tests/test_training_pipeline.py` — assert >= 6 artifacts
- `backend/app/features/ml_models/tft/tests/test_data_adapter.py` — un-skip serialize roundtrip

**Test Plan** (TDD):
1. `test_tft_training_produces_artifacts` — verify 4 TFT artifacts per horizon after training
2. `test_tft_serialize_roundtrip` — un-skip, verify model roundtrips through save/load
3. `test_full_ensemble_artifacts` — assert 6 artifacts after training (LSTM + 4 TFT + conformal)

**Acceptance Criteria**:
- `pytorch-forecasting` trains without `tuple indices` error
- `train_universe()` produces 6 artifacts (not 2)
- TFT serialize roundtrip test passes
- All existing S4 tests still pass

**Verification**: `uv run pytest app/features/ml_models/tft/ app/features/ml_models/tests/test_training_pipeline.py -v`

### P6.T0.S2: Snapshot Feature Distribution at Train Time

**Files to modify**:
- `backend/app/features/ml_models/service.py` — after loading training data, compute feature distribution histogram per feature column, store in `training_run.model_metadata`
- `backend/app/features/ml_models/tests/test_training_pipeline.py` — add assertion for feature_distribution

**Test Plan** (TDD):
1. `test_feature_distribution_snapshotted` — after training, model_metadata has feature_distribution with 31 feature keys
2. `test_feature_distribution_backward_compat` — loading old training run (missing distribution) returns null gracefully

**Acceptance Criteria**:
- Every training run stores feature_distribution in metadata
- 31 features x 10 bins each
- Null-safe reads for existing training runs

**Verification**: `uv run pytest app/features/ml_models/tests/test_training_pipeline.py -v`

---

## P6.T1: Monitoring Schema Finalize + Alert Service

**Effort**: M / 1 day | **Dependencies**: P6.T0 | **Risk**: Low

### P6.T1.S0: Alembic Merge Migration

**Files to create**:
- `backend/alembic/versions/merge_s1_s5_heads.py` — merge `d871d570373e` + `87167d0fe01e`

**Acceptance Criteria**: Single head after merge. `alembic upgrade head` works. `alembic downgrade -1` roundtrips.

### P6.T1.S1: Monitoring Tables Migration

**File to create**:
- `backend/alembic/versions/[rev]_add_monitoring_tables.py`

**Creates 3 tables**: `coverage_metrics`, `feature_drift_metrics`, `system_alerts` with partial index on `(resolved_at, severity) WHERE resolved_at IS NULL`.

**Acceptance Criteria**: 3 tables with all columns per design §9. Partial index present. upgrade/downgrade round-trip clean.

### P6.T1.S2: Monitoring Feature Module Stub

**Files to create**: `backend/app/features/monitoring/` with models.py, schemas.py, repository.py, service.py, router.py, dependencies.py, features.md

**Acceptance Criteria**: Models match design §9 column-for-column. Pydantic schemas for all CRUD operations.

### P6.T1.S3: Alert Service with Severity + Dedup

**Files**: repository.py (alert CRUD), service.py (AlertService with raise/dedup/acknowledge/resolve)

**Test Plan**: 7 tests — create, dedup, critical triggers notifier, info/warning skip, acknowledge, resolve, list-open filters resolved

**Acceptance Criteria**: raise_alert inserts with severity; same condition dedups; critical triggers notifier; info/warning don't

### P6.T1.S4: Slack Webhook Notifier (Config-Gated)

**File to create**: `backend/app/core/services/notifier.py`

**Test Plan**: 4 tests — noop when URL unset, posts to URL, swallows network error, no secrets in payload

**Acceptance Criteria**: Critical alert POSTs to Slack when SLACK_WEBHOOK_URL set. No-op when unset. Slack failure swallowed + logged.

---

## P6.T2: Coverage + Loss-Curve Signals

**Effort**: M / 1 day | **Dependencies**: P6.T1, S5 (resolved tickets) | **Risk**: Medium

### P6.T2.S1: Conformal Coverage Signal

**Files**: `backend/app/features/monitoring/signals/coverage.py`

Compute realized coverage per universe/horizon over 30/90d windows from resolved tickets. Write coverage_metrics. Raise COVERAGE_BREACH critical when sustained below 80%.

**Test Plan**: 5 tests — coverage computed, sustained breach alert, short sample skip, 30d+90d, exact calculation cross-check

### P6.T2.S2: Train/Val Loss-Curve Signal

**Files**: `backend/app/features/monitoring/signals/loss_curve.py`

Expose per-epoch train/val loss from training_runs.validation_metrics. Detect overfitting (train down + val plateau/up). Warning alert.

**Test Plan**: 4 tests — overfitting detected, both falling = no alert, short window skip, loss history exposed

---

## P6.T3: Correlation + Backtest-Drift + Freshness + Pipeline-Success

**Effort**: L / 2 days | **Dependencies**: P6.T1, S5 | **Risk**: Medium

### P6.T3.S1: Conviction-vs-Outcome Correlation

**Files**: `backend/app/features/monitoring/signals/correlation.py`

Spearman rank correlation between conviction_score and actual_return across resolved tickets. Sub-0.2 sustained → CONVICTION_UNPREDICTIVE warning.

**Test Plan**: 4 tests — perfect positive correlation, random sub-0.2 raises warning, insufficient sample skip, per-universe independence

### P6.T3.S2: Backtest Pass-Rate Drift

**Files**: `backend/app/features/monitoring/signals/backtest_drift.py`

Fraction of tickers passing >= 2 strategies per backtest run. Month-over-month downward trend > 5pp → warning.

**Test Plan**: 3 tests — pass rate computed, downward trend alert, stable rate no alert

### P6.T3.S3: Data Freshness + Pipeline Success

**Files**: `backend/app/features/monitoring/signals/freshness.py`

Freshness: time since last successful ingest per universe > 36h → INGEST_STALE critical.
Pipeline success: fraction of recent Prefect flows succeeding < 95% → warning.

**Test Plan**: 4 tests — stale raises critical, recent no alert, below 95% warning, healthy no alert

---

## P6.T4: Feature-Drift KL Signal

**Effort**: M / 1 day | **Dependencies**: P6.T1, P6.T0.S2 | **Risk**: Medium

### P6.T4.S1: KL Divergence Drift Signal

**Files**: `backend/app/features/monitoring/signals/drift.py`

Per-feature KL divergence between current 252d distribution and training distribution. Smoothed binning (epsilon to empty bins). Breach → FEATURE_DRIFT warning.

**Test Plan**: 5 tests — identical = zero, shifted = positive, empty bin not infinity, breach raises warning, missing training dist skipped

---

## P6.T5: Monitoring Flows + Wiring

**Effort**: M / 1 day | **Dependencies**: P6.T2, P6.T3, P6.T4 | **Risk**: Low

### P6.T5.S1: Monitoring Prefect Flows

**Files**: `orchestration/flows/conformal_coverage_check.py`, `orchestration/flows/daily_monitoring.py`

Coverage check daily 11pm ET. Combined monitoring flow with varied cadence for heavier signals. Register both in deployments.py.

**Acceptance Criteria**: Coverage-check + monitoring flows deployed + scheduled. Each signal writes metrics + raises alerts. On-failure hooks raise alerts.

### P6.T5.S2: Wire On-Failure Hooks Into All Existing Flows

**Files to modify**: daily_inference.py, weekly_backtest.py, weekly_retrain.py, outcome_resolution.py, daily_data_refresh.py

Replace 3 stubbed _write_system_alert() with real AlertService. Add alerting to 2 flows without it. FLOW_FAILED critical on failure.

**Acceptance Criteria**: Every flow raises critical on failure. Stubs replaced. Deliberate failure produces alert + Slack.

---

## P6.T6: Housekeeping Schedulers + Retention

**Effort**: M / 1 day | **Dependencies**: P6.T1, S4 | **Risk**: Low

### P6.T6.S1: Artifact Retention Reaper

**Files**: `orchestration/flows/artifact_retention.py`

Weekly (Sunday 11pm ET): archive model_artifacts > 6 months old (never active champion). Delete files via artifact store. Keep DB rows.

**Acceptance Criteria**: Reaper archives inactive >6mo. Champions untouched. DB rows preserved with archived_at.

### P6.T6.S2: Session Reaper + Partition Policy

**Files**: `core/services/scheduler.py` (new), `main.py` (lifespan registration)

Hourly in-process scheduler: delete expired sessions. Timescale retention documented (inactive v1). Confirm chunk intervals.

**Acceptance Criteria**: Hourly session reaper deletes expired sessions. Timescale retention documented. Chunk intervals confirmed.

---

## P6.T7: Model Health Dashboard UI

**Effort**: L / 2 days | **Dependencies**: P6.T1 | **Risk**: Low

### P6.T7.S1: Monitoring Overview + Per-Universe Model Card

**Files**: MonitoringPage.tsx (overhaul), HealthOverviewPage.tsx, ModelCardPage.tsx, API hooks

**Routes**: `/monitoring` (overview grid), `/monitoring/:universeId` (model card). HealthBadge (green/amber/red). Coverage/correlation per universe.

**Acceptance Criteria**: Overview shows per-universe health badges. Model card shows training, artifacts, validation metrics, coverage, recent tickets. 60s polling.

### P6.T7.S2: Coverage + Drift Signal Pages

**Files**: CoveragePage.tsx, DriftPage.tsx, CoverageChart.tsx, DriftHeatmap.tsx, CorrelationChart.tsx, LossCurveChart.tsx

Recharts charts: coverage with 90%/80% lines, drift heatmap/small-multiples, correlation with threshold, loss curves.

**Acceptance Criteria**: Coverage page with realized/nominal/breach. Drift page with per-feature KL. Correlation chart with threshold.

### P6.T7.S3: Backend Monitoring API Endpoints

**Files**: `backend/app/features/monitoring/endpoints/` — health, coverage, drift, alerts endpoints

```
GET  /api/v1/monitoring/health                   — overview
GET  /api/v1/monitoring/health/{universe_id}     — model card
GET  /api/v1/monitoring/coverage                 — coverage time series
GET  /api/v1/monitoring/drift                    — drift metrics
GET  /api/v1/monitoring/alerts                   — list open alerts
POST /api/v1/monitoring/alerts/{id}/acknowledge  — acknowledge
POST /api/v1/monitoring/alerts/{id}/resolve      — resolve
```

---

## P6.T8: Alerts UI + Prefect Runs Panel

**Effort**: M / 1 day | **Dependencies**: P6.T1, P6.T5 | **Risk**: Low

### P6.T8.S1: Alerts Surface

**Files**: AlertsPage.tsx, AlertsBanner.tsx (global), API hooks for acknowledge/resolve

Global banner for critical unresolved alerts on every page. List page with filters. Acknowledge + resolve mutations.

**Acceptance Criteria**: Open alerts listed with actions. Critical alerts show global banner on all pages. Filters work.

### P6.T8.S2: Pipeline Runs Panel

**Files**: PipelineRunsPage.tsx, PipelineRunsTable.tsx, usePipelineRuns.ts

Table of recent flow runs from Prefect API. Status badges. Pipeline success rate. Link out to Prefect UI.

**Acceptance Criteria**: Recent runs listed with status + timing. Success rate displayed. Prefect link-out works. In-progress surfaced.

---

## P6.T9: Full Playwright + Performance + Load-Sanity

**Effort**: L / 2 days | **Dependencies**: P6.T7, P6.T8 | **Risk**: Medium

### P6.T9.S1: Expand Playwright to All Critical Paths

**Files to create**: `e2e/tests/` — login.spec.ts, universes.spec.ts, monitoring.spec.ts, tickets.spec.ts, backtests.spec.ts, alerts.spec.ts

6 E2E test files covering all critical journeys. Each deterministic, /ready-gated, with seeded fixtures. External APIs mocked.

**Acceptance Criteria**: 6 specs covering all critical paths. Deterministic + /ready-gated. Pass in CI.

### P6.T9.S2: Performance Pass + Load-Sanity

**Files**: `backend/tests/load/test_load_sanity.py` — httpx concurrent async script

Profile hot paths. Load-sanity: 50 concurrent inbox + model-health requests. Confirm no pool exhaustion.

**Acceptance Criteria**: Hot-path queries profiled. Load-sanity passes. Findings + tuning documented.

---

## P6.T10: Autonomy Verification + Documentation

**Effort**: L / 2 days | **Dependencies**: All S6 tasks | **Risk**: Medium

### P6.T10.S1: Simulated Full-Week Autonomy Test

**Files**: `backend/tests/integration/test_autonomy_week.py`

Simulated week on accelerated time: data → features → backtest → retrain → 5x inference → outcome → monitoring. Assert no manual intervention.

**Acceptance Criteria**: All flows run end-to-end without intervention. Only deliberately-injected alerts fire. No unhandled exceptions.

### P6.T10.S2: Complete Runbooks + Monday-Morning Digest

**Files**: `docs/runbooks/` — manual-password-reset.md, colab-training.md, prefect-flow-recovery.md, alert-response.md, monday-morning-digest.md

Alert-response maps every code to cause+fix. Monday digest = operator's weekly checklist.

**Acceptance Criteria**: Every runbook complete. Alert-response covers every code. Monday digest documented. README complete.

### P6.T10.S3: features.md + Architecture Doc + v1 Completion Review

**Files**: `backend/app/features/monitoring/features.md`, `docs/architecture.md`, `docs/v1-completion-review.md`

Monitoring dev docs. Final architecture diagram. v1 checklist mapping design §2-§10 to shipped stages. Pipeline B handoff notes.

**Acceptance Criteria**: monitoring features.md + architecture doc complete. v1 checklist complete. Pipeline B handoff written.

---

## Appendix A: Parallel Execution Streams

| Stream | Tasks | Sub-tasks | Can start |
|--------|-------|-----------|-----------|
| **Foundation** | P6.T0 → T1 | T0.S1, T0.S2, T1.S0-S4 | Immediately |
| **Signals A** | P6.T2 | T2.S1, T2.S2 | After T1 |
| **Signals B** | P6.T3 | T3.S1, T3.S2, T3.S3 | After T1 |
| **Signals C** | P6.T4 | T4.S1 | After T1 + T0.S2 |
| **Flows** | P6.T5 | T5.S1, T5.S2 | After T2+T3+T4 |
| **Housekeeping** | P6.T6 | T6.S1, T6.S2 | After T1 |
| **Frontend A** | P6.T7 | T7.S1, T7.S2, T7.S3 | After T1 |
| **Frontend B** | P6.T8 | T8.S1, T8.S2 | After T1 + T7 |
| **Hardening** | P6.T9 | T9.S1, T9.S2 | After T7+T8+T5+T6 |
| **Final** | P6.T10 | T10.S1, T10.S2, T10.S3 | After all above |

## Appendix B: Full Task List (40 sub-tasks)

| Task | Sub | Description | Stream | Effort |
|------|-----|-------------|--------|--------|
| T0 | S1 | Fix TFT training compatibility | Foundation | M/4h |
| T0 | S2 | Snapshot feature distribution at train time | Foundation | S/3h |
| T1 | S0 | Alembic merge migration | Foundation | S/1h |
| T1 | S1 | Monitoring tables migration | Foundation | M/4h |
| T1 | S2 | Monitoring feature module stub (models, schemas) | Foundation | S/3h |
| T1 | S3 | AlertService with severity + dedup | Foundation | M/4h |
| T1 | S4 | Slack webhook notifier (config-gated) | Foundation | S/2h |
| T2 | S1 | Conformal coverage signal | Signals A | M/4h |
| T2 | S2 | Train/val loss-curve signal | Signals A | S/3h |
| T3 | S1 | Conviction-vs-outcome correlation | Signals B | M/4h |
| T3 | S2 | Backtest pass-rate drift | Signals B | S/3h |
| T3 | S3 | Data freshness + pipeline success | Signals B | M/4h |
| T4 | S1 | Feature-drift KL divergence | Signals C | M/4h |
| T5 | S1 | Conformal coverage check + daily monitoring flows | Flows | M/4h |
| T5 | S2 | Wire on-failure alerts into all existing flows | Flows | S/3h |
| T6 | S1 | Artifact retention reaper | Housekeeping | S/3h |
| T6 | S2 | Session reaper + partition policy | Housekeeping | S/3h |
| T7 | S1 | Monitoring overview + per-universe model card UI | Frontend A | L/1d |
| T7 | S2 | Coverage + drift signal pages UI | Frontend A | M/4h |
| T7 | S3 | Backend API endpoints for monitoring data | Frontend A | M/4h |
| T8 | S1 | Alerts surface (list + banner + ack/resolve) UI | Frontend B | M/4h |
| T8 | S2 | Pipeline runs panel + Prefect link-out UI | Frontend B | S/3h |
| T8 | S3 | Backend API for alert management + health summary | Frontend B | M/4h |
| T9 | S1 | Expand Playwright to all critical paths (6 specs) | Hardening | L/1d |
| T9 | S2 | Performance pass + load-sanity check | Hardening | M/4h |
| T10 | S1 | Simulated full-week autonomy integration test | Final | L/1d |
| T10 | S2 | Complete all runbooks + Monday-morning digest | Final | M/4h |
| T10 | S3 | features.md + architecture doc + v1 completion review | Final | M/4h |

## Appendix C: Verification Commands

```bash
# Backend: all monitoring tests
uv run pytest app/features/monitoring/ -v

# Backend: regression (S4 ML models)
uv run pytest app/features/ml_models/ -v -k "not slow"

# Backend: regression (S5 backtesting + tickets)
uv run pytest app/features/backtesting/ app/features/conviction_tickets/ -v

# Backend: lint
uv run ruff check app/features/monitoring/

# Frontend: all tests
pnpm vitest run

# Frontend: typecheck
pnpm tsc --noEmit

# E2E: Playwright
pnpm --prefix e2e exec playwright test

# Load sanity
uv run pytest tests/load/test_load_sanity.py -v

# Autonomy test
uv run pytest tests/integration/test_autonomy_week.py -v -m integration
```

## Appendix D: New Files Summary

| Area | Files to create | Files to modify |
|------|----------------|-----------------|
| Backend monitoring | ~25 new files | 0 (all new feature) |
| Backend orchestration | 2 new flows + deployments update | 5 existing flows (alert hooks) |
| Backend S4 patches | 0 | 2 (service.py, pyproject.toml) + 2 test files |
| Backend scheduler | 1 new (core/services/scheduler.py) | 1 (main.py lifespan) |
| Backend Alembic | 2 migrations (merge + monitoring) | 0 |
| Frontend | ~20 new files | 1 (App.tsx routes) + 1 (MonitoringPage.tsx overhaul) |
| E2E | 6 new Playwright specs | 0 |
| Docs | 5 runbooks + 3 docs | 2 existing runbooks (enhance) |
| Tests | Load sanity + autonomy test | 0 |
