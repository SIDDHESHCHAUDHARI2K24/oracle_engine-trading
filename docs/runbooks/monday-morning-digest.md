# Monday Morning Digest — Weekly Operator Checklist

Run through this checklist every Monday morning (or first business day after the weekend retrain /
backtest cycle completes). Estimated time: 10-15 minutes.

---

## Prerequisites

- Backend running: `http://localhost:8000`
- Prefect UI accessible: `http://localhost:4200`
- Frontend dashboard: `http://localhost:5173/health`

---

## Checklist

### 1. Open Alerts

- [ ] Navigate to `/health` — scan the alert severity column for each universe
- [ ] Any `critical` alerts? Address immediately. See [Alert Response Runbook](alert-response.md)
- [ ] Any `warning` alerts? Note and plan to investigate today
- [ ] Count of open alerts: should be trending toward zero over time

```bash
# Quick CLI check
curl -s http://localhost:8000/api/v1/monitoring/alerts | python -m json.tool | grep -E '"code"|"severity"'
```

### 2. Weekend Retrain — Champion Promotion

- [ ] Check Prefect UI for `weekly-retrain` flow run (Sundays 6am ET): status should be `Completed`
- [ ] For each universe, verify:
  - New `TrainingRun` row created with status `succeeded`
  - Champion/challenger promotion logic ran (check logs for "Promotion for universe…")
  - Active artifacts are updated (`model_artifacts.is_active = true` for the new run)
- [ ] If retrain failed for any universe: trigger a manual retrain now
  ```bash
  curl -X POST http://localhost:8000/api/v1/ml_models/trigger_retrain?universe_id=<id>
  ```

### 3. Coverage Metrics — Should Be Near 90%

- [ ] Navigate to `/health/coverage` — select each universe
- [ ] 30-day realized coverage should be **≥ 85%** (target: 90% for α=0.10)
- [ ] 90-day realized coverage should be **≥ 85%**
- [ ] Any horizon below 80%? Flag for investigation — conformal calibration may need a refresh
- [ ] Coverage trending down over 3+ weeks? Consider re-tuning the conformal α

### 4. Conviction Correlation — Should Be > 0.2

- [ ] Check the correlation chart on each universe's model card at `/health/{universe_id}`
- [ ] Spearman correlation between `conviction_score` and `actual_return` should be **> 0.2**
- [ ] Below 0.2 sustained? Review [CONVICTION_UNPREDICTIVE alert remediation](alert-response.md#conviction_unpredictive)
- [ ] Is correlation horizon-specific? T+1 may be noisy; T+5/T+10 should carry the signal

### 5. Data Freshness — Should Be < 24 Hours

- [ ] Check "Data Freshness" indicator on `/health` for each universe
- [ ] Last successful ingest should be **< 24 hours ago** (ideally ~4:30pm ET prior trading day)
- [ ] If > 36 hours: INGEST_STALE alert should be firing. Check [alert remediation](alert-response.md#ingest_stale)
- [ ] Verify the `daily_data_refresh` flow ran successfully in Prefect UI

```bash
# Quick CLI check
curl -s http://localhost:8000/api/v1/data_ingestion/status | python -m json.tool | grep -E "last_success|status"
```

### 6. Pipeline Success Rate — Should Be > 95%

- [ ] In Prefect UI, filter flow runs for the past 7 days
- [ ] Count `Completed` vs `Failed` runs across all flows
- [ ] Success rate should be **> 95%**
- [ ] If lower: identify the repeat-failing flow and investigate. See [Prefect Flow Recovery](prefect-flow-recovery.md)

### 7. Feature Drift — New Breaches

- [ ] Navigate to `/health/drift` for each universe
- [ ] Any features with `threshold_breached = true` on the most recent measurement?
- [ ] If yes:
  - 1-2 features with mild drift: note and monitor. Weekly retrain should absorb.
  - 5+ features with drift: consider an immediate retrain and review whether a market regime shift is underway
- [ ] Check the drift trend chart: is drift accelerating or stable?

### 8. Conviction Ticket Inbox — Sanity Check

- [ ] Navigate to `/tickets` — the inbox
- [ ] Spot-check: do the top-5 TRADABLE tickets make intuitive sense?
  - Reasonable conviction scores (67-85 range, not all 99+)
  - Reasonable predicted returns (not +50% on a mega-cap)
  - Conformal intervals look plausible
- [ ] Total TRADABLE count: note the baseline. If it suddenly spikes or drops to zero, investigate.
- [ ] Any RESOLVED tickets from last week worth reviewing for pattern recognition?

---

## Action Items from This Checklist

| Finding | Action |
|---|---|
| Any critical alert | Address immediately per [alert-response.md](alert-response.md) |
| Retrain failed | Manual retrain via API or Prefect re-run |
| Coverage < 80% | Plan retrain; check for regime shift |
| Correlation < 0.2 | Deeper investigation per alert runbook |
| Data stale > 36h | Check fetcher health; trigger manual ingest |
| Pipeline success < 95% | Identify failing flow; fix and re-run |
| Many drift breaches | Immediate retrain if sustained |

---

## Weekly Notes Template

```
Date: YYYY-MM-DD
Operator: ___________

Alerts:
  Open: ___ critical, ___ warning, ___ info
  New this week: _________________________________

Retrain:
  S&P 500: [ ] completed / [ ] failed
  Russell 1000: [ ] completed / [ ] failed
  Russell 2000: [ ] completed / [ ] failed

Coverage (T5, 30d):
  S&P 500: ____%  |  R1000: ____%  |  R2000: ____%

Correlation (Spearman, 90d):
  S&P 500: ____  |  R1000: ____  |  R2000: ____

Data Freshness: ____ hours ago
Pipeline Success Rate: ____%

Drift Breaches: ____ features across ____ universes

Tickets in Inbox: ____ TRADABLE

Notes:
_________________________________________________
_________________________________________________
```
