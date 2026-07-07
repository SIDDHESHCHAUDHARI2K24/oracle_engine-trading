# Prefect Flow Recovery Runbook

How to diagnose, recover from, and re-run failed Prefect flows.

---

## Prerequisites

- Prefect server running: `docker compose -f docker-compose.dev.yml up -d prefect-server prefect-worker`
- Prefect UI: `http://localhost:4200`
- Flows deployed: `uv run python -m app.orchestration.deployments`

---

## Flow Inventory

| Flow | Schedule | Covers |
|---|---|---|
| `daily-data-refresh` | Weekdays 4:30pm ET | OHLCV + macro ingest → feature engineering increment |
| `daily-inference` | Weekdays 5:30pm ET | Inference per universe → filter gate → emit tickets |
| `weekly-backtest` | Sundays 4am ET | 5-year 4-strategy backtest per universe |
| `weekly-retrain` | Sundays 6am ET | Walk-forward train LSTM + TFT Quad → champion promotion |
| `outcome-resolution` | Weekdays 5pm ET | Resolve tickets whose horizon ended today |
| `conformal-coverage-check` | Daily 11pm ET | Compute realized coverage → raise COVERAGE_BREACH if needed |
| `daily-monitoring` | Daily 10pm ET | Freshness, pipeline success, correlation (Mon/Thu), drift (Mon/Thu) |
| `artifact-retention` | Sundays 11pm ET | Archive inactive artifacts > 6 months old |

---

## Step 1: Check Prefect UI for Failure Details

1. Open `http://localhost:4200`
2. Navigate to **Flow Runs**
3. Filter by **State: Failed**
4. Click into the failed run → expand the failed task → read the stack trace

---

## Step 2: Common Failures and Fixes

### daily-data-refresh Failing

| Symptom | Likely Cause | Fix |
|---|---|---|
| `yfinance` timeout | Yahoo rate-limiting or outage | Wait 30 min, re-run. yfinance is throttled but self-heals. |
| `Alpaca API key invalid` | Paper account expired or key rotated | Renew at https://alpaca.markets; update `ALPACA_API_KEY` in `.env` |
| `EmptyDataError` on many tickers | Delisted symbols in universe | Run `uv run python scripts/seed_universes.py` to refresh constituents |
| `TimescaleDB connection refused` | Postgres is down | `docker compose -f docker-compose.dev.yml up -d postgres` |
| `disk full` | TimescaleDB hypertables not compressing | Run `uv run python scripts/housekeeping.py` to compress chunks |

### daily-inference Failing

| Symptom | Likely Cause | Fix |
|---|---|---|
| `MODEL_NOT_TRAINED` | No active artifacts for a universe | Manually trigger retrain: `POST /api/v1/ml_models/trigger_retrain` |
| `CUDA out of memory` | GPU memory exhausted | Reduce batch size; run inference on CPU if GPU is tight |
| `KeyError` on feature name | Feature schema mismatch between training and now | Run feature backfill: `POST /api/v1/feature_engineering/trigger` |

### weekly-retrain Failing

| Symptom | Likely Cause | Fix |
|---|---|---|
| OOM during LSTM training | Too many tickers in a large universe | Reduce batch size (256 → 128) or limit ticker count |
| `time_limit_exceeded` | Training exceeded the 4-hour task timeout | Increase `timeout_seconds` in the flow's task decorator |
| `NaN` in validation metrics | Corrupted feature data | Check feature_matrix for NaN rows: `psql -d mbi -c "SELECT count(*) FROM feature_matrix WHERE close IS NULL"` |
| TFT `QuantileLoss` error | pytorch-forecasting version mismatch | `uv sync` to ensure dependencies are consistent |

### weekly-backtest Failing

| Symptom | Likely Cause | Fix |
|---|---|---|
| `vectorbt` error on empty trades | Ticker has fewer than 200 bars | Skip tickers with < 1 year of history |
| Memory spike on large universe | vectorbt loads all tickers into memory | Process tickers in batches via the flow |

### Other Flows

| Flow | Common Failure | Fix |
|---|---|---|
| `outcome-resolution` | Missing close prices for resolution date | Ingest ran late — re-run ingest first, then outcome resolution |
| `conformal-coverage-check` | No resolved tickets in window | Normal for a cold start. Alert fires only after MIN_TICKET_COUNT (5) reached |
| `daily-monitoring` | Prefect API auth failure | Check `PREFECT_API_URL` in `.env` |
| `artifact-retention` | Permission denied on artifact files | Check `~/.mbi/artifacts/` permissions |

---

## Step 3: Re-running a Specific Flow

### Via Prefect UI (Recommended)

1. Open `http://localhost:4200`
2. Navigate to the flow's page
3. Click **Run** → **Quick Run** (or set custom parameters if needed)
4. Monitor the run in real-time

### Via API

```bash
# Trigger the daily data refresh
curl -X POST http://localhost:8000/api/v1/data_ingestion/trigger

# Trigger inference
curl -X POST http://localhost:8000/api/v1/ml_models/trigger_inference?universe_id=<id>

# Trigger retrain for a specific universe
curl -X POST http://localhost:8000/api/v1/ml_models/trigger_retrain?universe_id=<id>
```

### Via Prefect CLI

```bash
# From the backend directory
uv run python -c "
from app.orchestration.flows.daily_data_refresh import daily_data_refresh_flow
import asyncio
asyncio.run(daily_data_refresh_flow())
"
```

---

## Step 4: Manual Retrain Procedure

If the scheduled `weekly-retrain` flow failed and you need to retrain now:

```bash
cd backend

# 1. Verify data is fresh
curl -s http://localhost:8000/api/v1/data_ingestion/status | python -m json.tool

# 2. If not, trigger ingest first
curl -X POST http://localhost:8000/api/v1/data_ingestion/trigger

# 3. Trigger feature engineering (follows ingest automatically, but force if needed)
curl -X POST http://localhost:8000/api/v1/feature_engineering/trigger

# 4. Trigger retrain
curl -X POST http://localhost:8000/api/v1/ml_models/trigger_retrain?universe_id=<id>

# 5. Monitor progress in Prefect UI
```

The retrain flow will:
1. Create a `TrainingRun` row
2. Train LSTM on the 70% walk-forward window
3. Train 4 TFTs (one per horizon) in parallel
4. Fit the conformal calibrator on the 15% calibration window
5. Evaluate on the 15% validation window
6. Run champion/challenger promotion — new models replace old only if validation metrics improve

**Important**: Old artifacts stay `is_active = false`, not deleted. Rollback is always possible.

---

## Step 5: Manual Backtest Procedure

```bash
# Trigger backtest for a universe
curl -X POST http://localhost:8000/api/v1/backtests/trigger?universe_id=<id>

# Trigger for a single ticker
curl -X POST "http://localhost:8000/api/v1/backtests/trigger?universe_id=<id>&ticker_id=<ticker_id>"
```

A full-universe backtest can take 5-15 minutes depending on ticker count. Monitor in Prefect UI.

---

## Step 6: Preventative Measures

- [ ] **Set up Prefect notifications**: Configure Slack/email alerts in Prefect for flow failure events
- [ ] **Monitor disk space**: TimescaleDB hypertables grow ~1-2 GB/month with 3 universes
  ```bash
  df -h /var/lib/postgresql
  ```
- [ ] **Run housekeeping monthly**: `uv run python scripts/housekeeping.py` (compresses old chunks, vacuums)
- [ ] **Check `.env` API keys**: Alpaca paper accounts expire every 30 days — set a calendar reminder
- [ ] **Review flow logs weekly**: `docker compose logs backend | grep -i "error\|fail\|exception" | tail -50`
