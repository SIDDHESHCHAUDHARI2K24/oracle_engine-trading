# Alert Response Runbook

Operator guide for every alert code emitted by the monitoring system. All alerts are stored in
`system_alerts` and surfaced on the `/health` dashboard and via `GET /api/v1/monitoring/alerts`.

---

## Alert Severities

| Severity | Meaning | Expected Response Time |
|---|---|---|
| `critical` | Pipeline is broken or producing unreliable output | Immediate — within 4 business hours |
| `warning` | Degradation detected; may become critical if sustained | Same business day |
| `info` | FYI; no action required unless it escalates | Next business day |

---

## Alert Codes

### COVERAGE_BREACH

| Field | Value |
|---|---|
| Severity | `critical` |
| Signal | Conformal coverage |
| Trigger | Realized coverage below 80% sustained across 5 consecutive measurements |
| Check frequency | Daily, via `conformal_coverage_check` flow (11pm ET) |

**Cause**: The conformal prediction intervals are too narrow — actual returns are falling outside the
predicted 90% interval more than they should. The model is overconfident.

**Remediation**:
1. Open the coverage chart at `/health/coverage` — check which universe and horizon triggered it
2. Look for a regime shift: did a sudden volatility spike break the calibration?
3. **Retrain the model**: trigger `POST /api/v1/ml_models/trigger_retrain?universe_id=<id>` or wait for the Sunday 6am ET weekly retrain
4. Verify after retrain: coverage should recover to near 90% within 5-10 trading days

**Do NOT ignore**: Sustained coverage below 80% means the ensemble is lying about its intervals.
Conviction tickets emitted during this period are unreliable.

---

### INGEST_STALE

| Field | Value |
|---|---|
| Severity | `critical` |
| Signal | Data freshness |
| Trigger | No successful `IngestRun` in the past 36 hours |

**Cause**: The daily 4:30pm ET data refresh is not completing. Possible reasons:
- yfinance is down or rate-limiting
- Alpaca API credentials expired
- TimescaleDB is unreachable
- Prefect worker is not running

**Remediation**:
1. Check the Prefect UI at `http://localhost:4200` — look at the `daily_data_refresh` flow history
2. Check the backend logs for fetcher errors: `docker compose logs -f backend | grep -i "fetch.*error"`
3. **Trigger a manual ingest**: `POST /api/v1/data_ingestion/trigger`
4. If yfinance is the problem, verify Alpaca fallback is configured:
   ```bash
   grep ALPACA .env
   ```
5. If all sources are down, wait and re-trigger. The ingest is idempotent — re-running is always safe.

---

### FLOW_FAILED

| Field | Value |
|---|---|
| Severity | `critical` |
| Signal | Prefect task execution |
| Trigger | Any Prefect task raises an unhandled exception |

**Cause**: A Prefect flow task failed. This is a catch-all for any component-level failure during
orchestrated runs (ingest, inference, retrain, monitoring, etc.).

**Remediation**:
1. Open the Prefect UI at `http://localhost:4200` — find the failed flow run
2. Click into the failed task to see the stack trace
3. Identify the root cause from the exception and the `system_alerts.message` field
4. Fix the underlying issue (see [Prefect Flow Recovery](prefect-flow-recovery.md))
5. Re-run the flow from the Prefect UI or via API

---

### FEATURE_DRIFT

| Field | Value |
|---|---|
| Severity | `warning` |
| Signal | Feature drift (KL divergence) |
| Trigger | Any feature's KL divergence between current 252-day distribution and training distribution exceeds 0.3 |

**Cause**: The statistical properties of the market data have changed since the model was trained.
This is common during regime changes (volatility spikes, sector rotations, macro shocks).

**Remediation**:
1. Open the drift heatmap at `/health/drift` — identify which feature(s) breached
2. Common culprits: `vix`, `volatility_20d`, `returns_*` during market turbulence
3. If 1-2 features drifted mildly: monitor. Scheduled weekly retrain should absorb the shift.
4. If many features drifted (5+): **trigger an immediate retrain**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/ml_models/trigger_retrain?universe_id=<id>
   ```
5. Review the drift trend over the past 30 days to see if it's accelerating

**Threshold tuning**: Edit `FEATURE_DRIFT_THRESHOLD` in `backend/app/features/monitoring/signals/drift.py`.

---

### CONVICTION_UNPREDICTIVE

| Field | Value |
|---|---|
| Severity | `warning` (escalates from `info` after 3 sustained measurements) |
| Signal | Conviction-vs-outcome correlation |
| Trigger | Spearman rank correlation between `conviction_score` and `actual_return` < 0.2 for 3 consecutive checks |

**Cause**: High-conviction tickets are not predicting direction correctly. The conviction score is
decoupled from actual outcomes.

**Remediation**:
1. Open the correlation chart on the model health dashboard
2. Check if this is horizon-specific (e.g., T+1 is broken but T+15 is fine)
3. Look for data quality issues: did a bad set of feature rows slip through?
4. Check whether the backtest pass rate also dropped (indicating a broader regime shift)
5. **Retrain**: the model may have drifted. Trigger manually or wait for Sunday.
6. If post-retrain correlation stays low, re-examine the conviction score formula in `conviction_tickets/scoring/risk_adjusted.py`

---

### OVERFITTING_DETECTED

| Field | Value |
|---|---|
| Severity | `warning` |
| Signal | Train/val loss curve divergence |
| Trigger | Train loss decreasing while validation loss increasing over the last 5 epochs of the latest training run |

**Cause**: The model is memorizing noise in the training data rather than learning generalizable patterns.

**Remediation**:
1. Open the training run detail at `/model-health/{universe_id}/training-history`
2. Confirm the divergence pattern visually on the loss curve chart
3. **Reduce epochs**: lower `max_epochs` in the training config
4. **Increase dropout**: bump LSTM dropout from 0.3 to 0.4 or 0.5
5. **Increase weight decay**: raise `weight_decay` in AdamW
6. **Check train/cal/val split sizes**: 70/15/15 ratio may need adjustment if training data is sparse
7. Re-trigger retrain with adjusted hyperparameters

---

### BACKTEST_DRIFT

| Field | Value |
|---|---|
| Severity | `warning` (drop > 5pp), `info` (drop > 2pp) |
| Signal | Backtest pass-rate trend |
| Trigger | Pass rate drops > 5 percentage points between consecutive weekly backtest runs |

**Cause**: Tickers that previously passed ≥2 strategies are now passing fewer. The market regime may
have shifted, rendering prior strategy edges less exploitable.

**Remediation**:
1. Open the backtest dashboard at `/backtests/{universe_id}`
2. Identify which strategies are losing passes (mean_reversion, momentum_cross, etc.)
3. A gradual decline over 3+ weeks: **market regime shift** — expected. No immediate action; the
   filter gate will naturally emit fewer tickets. Monitor.
4. A sudden drop: check for data quality issues or a bug in the backtest engine
5. If the decline persists past 4 weeks, review strategy parameters or consider adding new strategies

**Note**: BACKTEST_DRIFT is not always actionable. It is a diagnostic signal, not a failure. If the
pipeline is healthy and conviction correlation remains above 0.2, low pass rates are signal, not noise.

---

### PIPELINE_SUCCESS_LOW

| Field | Value |
|---|---|
| Severity | `warning` |
| Signal | Pipeline run success rate |
| Trigger | Less than 95% of Prefect flow runs succeed over the past 7 days |

**Cause**: One or more flows are failing at a rate that indicates a systemic problem rather than
occasional transient errors.

**Remediation**:
1. Open the Prefect UI at `http://localhost:4200` — sort by "Failed"
2. Identify which flow is the repeat offender (daily_data_refresh, daily_inference, etc.)
3. Check `system_alerts` for related `FLOW_FAILED` entries with matching timestamps
4. Common causes:
   - **Database connection pool exhaustion**: check `max_overflow` in the DB config
   - **Memory pressure**: retrain on a large universe may OOM the worker
   - **API rate limiting**: external source hitting its limit
5. Fix the root cause, then re-run the failing flows from Prefect

---

## Acknowledge and Resolve Alerts

Via API:
```bash
# Acknowledge
curl -X POST http://localhost:8000/api/v1/monitoring/alerts/{alert_id}/acknowledge

# Resolve
curl -X POST http://localhost:8000/api/v1/monitoring/alerts/{alert_id}/resolve
```

Via the frontend: each alert on `/health` has Acknowledge and Resolve buttons.

**Best practice**: Acknowledge on first look (so others know it's being handled). Resolve only after
the underlying issue is confirmed fixed and verified.
