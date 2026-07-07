# Feature: Data Ingestion (Block A1)

## Purpose

The numerical data backbone of Pipeline A. Ingests daily OHLCV bars for every active ticker across all universes, plus 7 FRED macroeconomic series. Provides transparent failover across three OHLCV sources (yfinance → Alpaca → Stooq), resumable cold-start backfill, and calendar-aware gap detection.

## Architecture

```
Universe.active_tickers
       │
       ▼
NumericalOrchestrator
       │
  ┌────┴──────────────┐
  ▼                   ▼
DataFetcher ABC    FREDFetcher (macro)
  │
  ├─ YahooFinanceFetcher (primary)
  ├─ AlpacaFetcher (secondary, failover)
  └─ StooqFetcher (last-resort CSV)
       │
       ▼
  ohlcv_bars (TimescaleDB hypertable)
  macro_observations (TimescaleDB hypertable)
       │
       ▼
  IngestRun (audit row)
```

## Tables

| Table | Type | Partition Key |
|---|---|---|
| `ohlcv_bars` | TimescaleDB hypertable | `bar_date` |
| `macro_observations` | TimescaleDB hypertable | `observed_date` |
| `ingest_runs` | Plain table | — |

### Chunk Configuration

Both hypertables use 1-month chunk intervals (`set_chunk_time_interval`). TimescaleDB auto-creates chunks on insert — no manual partition management is needed. A retention policy is documented as a future hook (not active in v1).

## Failover Chain

1. **YahooFinanceFetcher** (primary): `yfinance.download()`, ~2000 req/hr/IP
2. **AlpacaFetcher** (secondary): `alpaca-py` StockHistoricalDataClient, free paper account
3. **StooqFetcher** (last-resort): Direct CSV download from stooq.com

Fetchers inherit `DataFetcher` ABC and return identical schemas. The `source` column on each bar records which fetcher won. Failover is per-source (not per-symbol): if yfinance fails for all symbols, Alpaca is tried for the remaining, then Stooq.

## Per-Ticker Isolation

One ticker's total failure does not abort the batch. Failed tickers land in `IngestRun.failed_tickers`. If >3 tickers fail in a batch, a `DataPipelineAlert` is raised (logs via loguru; future alert hook reserved).

## Cleaning Rules

- **Timezone stripping**: `df.index.tz_localize(None)` — non-negotiable for TimescaleDB merges
- **No NaNs in OHLCV**: Dropped; empty returns treated as fetch failure
- **Macro forward-fill**: Aligned to NYSE trading calendar in the orchestrator during feature engineering (S3)
- **Leading-NaN drop**: Rows before a ticker's first valid OHLCV bar are dropped
- **Schema enforcement**: dtypes coerced (`float64` for prices, `int64` for volume)

## Trading Calendar

NYSE sessions via `pandas-market-calendars`. The calendar is the single source of truth for:
- Which dates should have bars (`expected_bars`)
- Gap detection (`detect_gaps` — compares expected vs present)
- Macro forward-fill alignment (S3)

## Microeconomic Series (FRED)

| FRED ID | Standardized Column |
|---|---|
| `DFF` | `fed_funds_rate` |
| `CPIAUCSL` | `cpi` |
| `UNRATE` | `unemployment` |
| `GDP` | `gdp` |
| `T10Y2Y` | `yield_spread_10y_2y` |
| `VIXCLS` | `vix` |
| `BAMLH0A0HYM2` | `high_yield_spread` |

## Trigger Modes

| Mode | Trigger | Frequency |
|---|---|---|
| `cold_start` | `scripts/initial_backfill.py` | Once at install |
| `incremental` | Prefect flow `daily_data_refresh` | Weekdays ~4:30pm ET |
| `on_demand` | `POST /api/v1/data_ingestion/trigger` | User-initiated |
| `gap_fill` | Triggered by daily flow | As needed |

## Resumability

The cold-start backfill is resumable via `INSERT ... ON CONFLICT (ticker_id, bar_date) DO UPDATE` in the OHLCV repository. Interrupting and re-running skips already-present data (idempotent). Full Russell-3000 backfill expects ~1.5-2 hours and ~1.5M rows.

## Testing Strategy

- **Mocked in CI**: All fetcher tests use recorded fixtures; no live network calls
- **`@pytest.mark.live`**: Manual smoke tests against real APIs (CI-skipped)
- **Integration tests**: Mocked fetchers at the orchestrator boundary + real test DB

## Future Hooks

- Polygon.io / Alpha Vantage: New `DataFetcher` subclasses; orchestrator wiring is one line
- Retention policy: `add_retention_policy` on hypertables (not active in v1)
- Prefect alert routing: On-failure hook stubbed; writes to `system_alerts` in S6
