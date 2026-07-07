# Cold-Start Ingestion Runbook

## Prerequisites

1. **All API keys configured** in `.env`:
   - `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` (free paper-trading account)
   - `FRED_API_KEY` (free at https://fred.stlouisfed.org/docs/api/api_key.html)
2. **TimescaleDB running** (port 5433): verify with `make db-check`
3. **Alembic migrations applied**: `make migrate` (or `cd backend && uv run alembic upgrade head`)
4. **Universes seeded**: S&P 500, Russell 1000, Russell 2000 + any custom universes
5. **Prefect server running**: `docker compose -f docker-compose.dev.yml up -d prefect-server prefect-worker`
6. **`prefect` database created**: `uv run python scripts/setup_prefect_db.py`

Run the live smoke test first as a pre-backfill sanity check:
```bash
cd backend && uv run python -m pytest app/features/data_ingestion/tests/ -v -m "live" --no-header
```

## Full Backfill

```bash
cd backend && uv run python scripts/initial_backfill.py
```

### Expected Runtime

| Universe Scope | ~Tickers | ~Bars | ~Runtime |
|---|---|---|---|
| S&P 500 only | ~500 | ~250,000 | ~15 min |
| S&P 500 + Russell 1000 + Russell 2000 | ~3,000 | ~1,500,000 | ~1.5–2 hr |

Runtime varies with yfinance availability (throttling, outages). With heavy Alpaca fallback, expect ~2× longer.

### Options

```bash
# Single universe
uv run python scripts/initial_backfill.py --universe sp500

# Smaller batches (for slower connections)
uv run python scripts/initial_backfill.py --batch-size 25

# Longer/shoter history
uv run python scripts/initial_backfill.py --years 3
```

## What Happens

1. Resolves all active tickers from universes (or the specified one)
2. Batches tickers (50 by default)
3. For each batch:
   - Tries yfinance → Alpaca → Stooq
   - Inserts bars with `ON CONFLICT` upsert (idempotent)
   - Fetches all 7 macro series via FRED
   - Logs progress: "Batch 3/60, 150 tickers done, 2 failed"
4. Reports final summary: total bars, total macro rows, failed tickers list

## Failure Recovery

### Interrupted mid-backfill
The script is **resumable**. Just re-run it — the `ON CONFLICT (ticker_id, bar_date) DO UPDATE` pattern means already-present bars are skipped (no duplicates, no wasted time).

### yfinance returns empty
yfinance sometimes silently returns empty DataFrames for valid symbols. The `EmptyDataError` detection triggers failover to Alpaca/Stooq. If all sources fail for a ticker, it lands in `failed_tickers`.

### Partial completion
If some tickers failed but others succeeded, the `IngestRun.status` will be `partial`. The monitoring panel shows the failed count. Re-running backfills the failures without redoing successes.

### Live-API flakiness
yfinance and FRED can be unreliable. Re-running is always safe — the upsert makes it idempotent. If yfinance is down for an extended period, Alpaca+Stooq cover the OHLCV path.

## Post-Backfill Verification

1. Check the monitoring panel: `GET /api/v1/data_ingestion/status`
2. Query a specific ticker: `GET /api/v1/data_ingestion/bars?ticker_id=<UUID>&start=2024-01-01&end=2026-06-01`
3. Verify the Prefect UI shows the daily flow registered: http://localhost:4200

## Daily Incremental

After backfill, the daily Prefect flow takes over:
```
Prefect flow: daily_data_refresh
Schedule: weekdays 4:30pm ET (after market close)
Mode: incremental (only fetches bars after each ticker's latest present date)
+ Auto gap-fill for up to 30 trading days
```

The daily flow can be triggered on-demand via the API:
```bash
curl -X POST http://localhost:8000/api/v1/data_ingestion/trigger
```
