# MBI Labs Oracle Engine — Pipeline A v1 Design Document

> **Status**: Brainstorming complete. All features and decisions locked with explicit user approval.
> **Date**: 28 May 2026
> **Scope**: Pipeline A — the Deep Learning Math Engine. A self-improving research-grade ML pipeline that ingests OHLCV + macroeconomic data across multiple equity universes, engineers a 31-dimensional feature tensor, trains a Bi-LSTM and a Temporal Fusion Transformer Quad-Array per universe, calibrates predictions with locally-weighted split conformal prediction, validates via four backtest strategies, and emits filtered Conviction Tickets for human review. Pipeline B (LLM Agent Swarm, Fusion Engine, paper-trading sandbox) is explicitly out of scope for v1.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Feature 1 — Auth & User Accounts](#2-feature-1--auth--user-accounts)
3. [Feature 2 — Universe Management](#3-feature-2--universe-management)
4. [Feature 3 — Data Ingestion (Block A1)](#4-feature-3--data-ingestion-block-a1)
5. [Feature 4 — Feature Engineering (Blocks A2 + A3)](#5-feature-4--feature-engineering-blocks-a2--a3)
6. [Feature 5 — ML Models (Blocks A4, A5, A6)](#6-feature-5--ml-models-blocks-a4-a5-a6)
7. [Feature 6 — Backtesting (Block A7)](#7-feature-6--backtesting-block-a7)
8. [Feature 7 — Conviction Tickets (Block A8 + Scoring)](#8-feature-7--conviction-tickets-block-a8--scoring)
9. [Feature 8 — Monitoring & Model Health](#9-feature-8--monitoring--model-health)
10. [Feature 9 — Orchestration (Prefect Flows)](#10-feature-9--orchestration-prefect-flows)
11. [Cross-cutting Patterns](#11-cross-cutting-patterns)
12. [Master Data Model Summary](#12-master-data-model-summary)
13. [Repository Architecture](#13-repository-architecture)
14. [Deviations From the Original Spec](#14-deviations-from-the-original-spec)
15. [Future-Friendly Hooks (deferred from v1)](#15-future-friendly-hooks-deferred-from-v1)

---

## 1. Tech Stack

| Layer | Decision |
|---|---|
| Backend framework | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Database | PostgreSQL 16 + **TimescaleDB extension** (hypertables for OHLCV, macro, features) |
| Migrations | Alembic (separate at `backend/alembic/`, single source of truth) |
| Backend pkg mgmt | uv |
| Caching | **Deferred** — repository abstraction is cache-friendly; add Valkey when load demands |
| ML framework | PyTorch 2.2+ |
| Specialized ML libs | `pytorch-forecasting` (TFT), `pytorch-lightning` (training loops), `TA-Lib` (technical indicators), `vectorbt` (backtests), `scikit-learn` (scaling only — conformal is custom) |
| Object/artifact storage | Local filesystem at `~/.mbi/artifacts/` for v1; MinIO/S3 swap point in `core/services/artifact_store.py` |
| Workflow orchestrator | **Prefect 3** (self-hosted, sharing the same Postgres) |
| Background scheduler (in-process) | Custom async scheduler in `core/services/scheduler.py` for non-Prefect periodic tasks |
| Frontend | Vite + React 18 + **TypeScript strict** |
| Frontend structure | Feature-focused (mirrors backend feature names) |
| Routing | React Router v6 |
| Server state | TanStack Query v5 |
| Forms | React Hook Form + Zod |
| Styling | Tailwind + shadcn/ui |
| Charting (financial) | **TradingView Lightweight Charts** (~45 KB, MIT) |
| Charting (general) | Recharts |
| Tables | TanStack Table (headless) |
| Client state | Zustand (minimal — auth slice, transient UI state) |
| Backend testing | pytest + pytest-asyncio |
| Frontend testing | vitest + @testing-library/react |
| E2E testing | Playwright (small critical-path suite) |
| Linting / format | **ruff** (backend), ESLint flat config + Prettier (frontend) |
| Logging | **loguru** (per the manifesto's Rule 2) |
| Real-time strategy | **Polling everywhere** (no SSE/WS/webhooks v1) |
| Deployment | Local dev for v1; designed for Railway/cloud later |
| Data sources (locked) | **yfinance** (primary OHLCV), **FRED** (macro), **Alpaca Market Data** (secondary OHLCV, requires free paper-trading account), **Stooq** (last-resort CSV fallback) |
| Data sources (interface-preserved, deferred) | Polygon.io, Alpha Vantage |
| Email infra | Deferred (single hardcoded admin v1; manual reset via admin CLI) |
| Auth | JWT, single hardcoded admin user. Database schema reserves `user_id` columns for multi-user. |
| Observability | loguru JSON logs to stdout, Prefect dashboard for flow state, per-feature `features.md` for system map. Prometheus/OTel deferred. |

---

## 2. Feature 1 — Auth & User Accounts

### Identity Model

- **Single hardcoded admin user** for v1, created at first boot via `scripts/seed_admin.py`.
- Multi-user-ready schema: `users` table, `sessions` table, `user_id` foreign keys on every tenant-scoped table from day one (always `NULL` or the admin's UUID in v1).
- No team/membership model in v1 — Pipeline A is single-tenant. Tenant boundary lives at `user_id`, not at `team_id`. Adding teams later is one migration.

### Login

- `POST /api/v1/auth/login` with `{email, password}` → returns JWT (`HS256`, 24h expiry, `user_id` claim).
- Frontend stores JWT in **memory only** (`Zustand` slice) and a refresh token in a `HttpOnly Secure SameSite=Strict` cookie.
- Refresh flow: `POST /api/v1/auth/refresh` reads cookie, issues new JWT.

### Sessions

- Postgres-backed. Refresh tokens stored hashed. Sliding 30-day expiry.
- Server-side revocable; logout deletes the session row.
- "Log out everywhere" supported (delete all sessions for `user_id`).

### Roles & Permissions

| Action | Admin (v1) |
|---|:---:|
| Everything | ✅ |

A `role` column with enum `('admin','editor','viewer')` is reserved on `memberships` (not used in v1) so multi-user differentiation is a no-schema-change rollout.

### Security & Ops

- Rate limiting (`slowapi`) per-IP on login: 10/min.
- Passwords hashed with `argon2-cffi` (more modern than bcrypt; same library decision pattern as Feenix's lookup).
- Manual password reset: `scripts/reset_password.py` (typer CLI). Generates a one-time token, prints to stdout.

### Frontend Surfaces

Under `features/auth/`:
- `/login`
- `/settings/account` (change password, view active sessions, log-out-everywhere)

### Tables

```sql
users(
  id UUID PK, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  full_name TEXT,
  is_admin BOOLEAN DEFAULT false,
  email_verified_at TIMESTAMPTZ NULL,    -- reserved for v2
  email_verification_token TEXT NULL,    -- reserved for v2
  created_at, updated_at
)

sessions(
  id UUID PK, user_id FK,
  refresh_token_hash TEXT NOT NULL,
  created_at, last_used_at, expires_at,
  user_agent TEXT, ip INET
)
-- index on refresh_token_hash for fast lookup
```

---

## 3. Feature 2 — Universe Management

### Concept

A **Universe** is a named, versioned basket of tickers (e.g., "S&P 500", "Russell 2000", "Custom Tech 50") that defines the scope of one end-to-end Pipeline A run. Every downstream artifact (feature matrix, trained model, conviction ticket) is scoped to a specific universe. **Each universe gets its own LSTM and TFT Quad-Array.**

### Membership Model

- Universe → many Tickers via `universe_memberships` join table.
- A ticker can belong to many universes (e.g., AAPL is in both S&P 500 and Tech 50).
- Universe membership is **time-aware**: each row has `added_at` and `removed_at TIMESTAMPTZ NULL`, supporting point-in-time queries for survivorship-bias-resistant backtesting.

### Ticker Identity

- The `tickers` table is the canonical ticker registry (one row per symbol).
- Holds metadata: `symbol`, `exchange`, `asset_type` (`equity` | `etf` | reserved: `crypto` later), `is_active`, `first_seen_at`, `last_seen_at`.
- Pipeline A only fetches data for tickers that are **active in at least one universe**.

### Universe Operations

| Action | Endpoint |
|---|---|
| Create | `POST /api/v1/universes` |
| List | `GET /api/v1/universes` |
| Detail | `GET /api/v1/universes/{id}` |
| Update metadata | `PATCH /api/v1/universes/{id}` |
| Soft delete | `DELETE /api/v1/universes/{id}` |
| Add tickers | `POST /api/v1/universes/{id}/membership` (bulk, accepts list) |
| Remove tickers | `DELETE /api/v1/universes/{id}/membership/{ticker_id}` |
| Snapshot membership | `GET /api/v1/universes/{id}/membership?at=2026-01-15` (point-in-time) |
| Import from CSV | `POST /api/v1/universes/{id}/membership:import` |

### Universe Lifecycle & Retraining

- **Membership change triggers cold-start consideration.** Removing one ticker from S&P 500 is fine — the model uses the current membership snapshot at training time. Adding a brand-new universe creates a new model artifact slot.
- New universe → no model yet. Inference returns `204` for that universe until the first weekly retrain ingests its data and trains it.
- A `seed_universes.py` script bootstraps the three v1 universes (S&P 500, Russell 1000, Russell 2000) from a checked-in CSV of constituent tickers.

### Frontend Surfaces

Under `features/universes/`:
- `/universes` — list, with ticker count and last-retrain badge
- `/universes/new` — create form
- `/universes/{id}` — detail: membership table, last-retrain status, link to model_health for this universe
- `/universes/{id}/edit` — edit form

### Tables

```sql
universes(
  id UUID PK, user_id FK users.id NULL,   -- NULL = system-managed (S&P 500, Russell 1000, Russell 2000)
  name TEXT NOT NULL, description TEXT NULL,
  display_name TEXT NOT NULL,
  is_system_managed BOOLEAN DEFAULT false,
  created_at, updated_at, deleted_at TIMESTAMPTZ NULL,
  UNIQUE(user_id, name)
)

tickers(
  id UUID PK,
  symbol TEXT UNIQUE NOT NULL,             -- "AAPL"
  exchange TEXT,                            -- "NASDAQ"
  asset_type ENUM('equity','etf'),          -- reserved: 'crypto'
  is_active BOOLEAN DEFAULT true,
  first_seen_at TIMESTAMPTZ, last_seen_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',              -- sector, market cap snapshot, etc.
  created_at, updated_at
)

universe_memberships(
  id UUID PK,
  universe_id FK universes.id ON DELETE CASCADE,
  ticker_id FK tickers.id,
  added_at TIMESTAMPTZ NOT NULL,
  removed_at TIMESTAMPTZ NULL,              -- NULL = still active
  added_by FK users.id NULL,
  UNIQUE(universe_id, ticker_id, added_at)
)
-- index on (universe_id, removed_at) for "active members" queries
-- index on (ticker_id) for "which universes is this ticker in"
```

---

## 4. Feature 3 — Data Ingestion (Block A1)

> **Spec reference**: Block A1 (Numerical Data Ingestion Layer). This feature implements `mbi.data.*` from the spec.

### Pipeline

```
Universe.active_tickers ─┐
                         │
                         ▼
                  NumericalOrchestrator
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
   YahooFinance         FREDFetcher
   Fetcher (primary)    (macro, uncontested)
        │ 3× retry fail
        ▼
   AlpacaFetcher (free fallback, paper-account-backed)
        │ 3× retry fail
        ▼
   StooqFetcher (CSV last resort)
        │
        ▼
   OHLCV per ticker ──► OHLCVBar (TimescaleDB hypertable)
   Macro series      ──► MacroObservation (TimescaleDB hypertable)
                         │
                         ▼
                  IngestRun row (status, timing, error log)
                         │
                         ▼
                  Block A2 (Feature Engineering)
```

### Data Sources & Failover Order

| Source | Library | Use | Rate limits |
|---|---|---|---|
| Yahoo Finance | `yfinance>=0.2.50` | **Primary** — daily OHLCV per ticker | ~2000/hr/IP, unofficial |
| FRED | `fredapi>=0.5.2` | Macro series (uncontested) | 100/day (we use 7 series; trivial) |
| Alpaca Market Data | `alpaca-py>=0.30` | **Secondary OHLCV** — failover, plus cross-validator on close prices | Free with paper account; generous limits |
| Stooq | Direct CSV download via `httpx` | **Last-resort** OHLCV CSV scrape | None formally |
| Polygon.io, Alpha Vantage | (interface preserved) | Deferred — concrete fetchers can drop in later | Paid; deferred |

The `DataFetcher` Abstract Base Class (per spec a1.2) lives in `features/data_ingestion/shared/fetcher_base.py`. All concrete fetchers inherit. The orchestrator iterates primary → secondary → tertiary on failure.

### Macroeconomic Series (per spec a1.4)

| FRED Series ID | Standardized column | Description |
|---|---|---|
| `DFF` | `fed_funds_rate` | Federal Funds Effective Rate |
| `CPIAUCSL` | `cpi` | Consumer Price Index |
| `UNRATE` | `unemployment` | Unemployment Rate |
| `GDP` | `gdp` | Gross Domestic Product |
| `T10Y2Y` | `yield_spread_10y_2y` | 10Y minus 2Y Treasury Yield |
| `VIXCLS` | `vix` | CBOE Volatility Index |
| `BAMLH0A0HYM2` | `high_yield_spread` | High-Yield Master II OAS |

Macro is forward-filled to the trading calendar in the orchestrator (per spec). A `stale_macro=True` flag is set on the `IngestRun` row if any series's most recent observation is >30 days old.

### Backfill vs Incremental

- **Cold-start backfill**: First-time setup. Pulls 2 years of daily OHLCV for every ticker in every universe. Batched (50 tickers/batch on yfinance to stay polite). Triggered by `scripts/initial_backfill.py`.
- **Daily incremental**: Each trading day after market close, fetch only the new day's bar for every active ticker. Macro pulled in the same flow (FRED publishes on its own cadence; we just take the latest).
- **Gap fill**: If `IngestRun` history shows a missing date for any ticker, the daily flow detects it and triggers a targeted refetch for the gap.

### Resilience (per spec a1.3)

- `tenacity` retry: `@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3))` on every fetcher's `fetch()` method.
- Per-ticker isolation: if AAPL fails 3 times, MSFT still proceeds. Failed tickers are logged into `IngestRun.failed_tickers` and surfaced as a dashboard alert.
- If >3 tickers in a batch fail → `DataPipelineAlert` is raised (logged loudly via loguru; a future Slack/email hook is reserved).

### Data Cleaning Rules (per spec a1.3, a1.5)

- **Timezone stripping**: `df.index = df.index.tz_localize(None)` on every fetched OHLCV frame. This is non-negotiable — TimescaleDB merges break if tz-aware and tz-naive indexes mix.
- **NaN policy**: Raw OHLCV must have **no NaNs** in OHLCV columns. Macro NaNs trigger forward-fill. If forward-fill can't resolve a leading NaN (i.e., the series didn't exist yet), the orchestrator drops those leading rows from the merged dataset.
- **Schema enforcement**: After fetch, the orchestrator asserts dtypes (`float64` for prices, `int64` for volume). Mismatches log a warning and coerce.

### Trigger Modes

| Mode | Trigger | Frequency |
|---|---|---|
| Cold-start backfill | `scripts/initial_backfill.py` (manual, once) | Once at install |
| Daily refresh | Prefect flow `daily_data_refresh.py` | Daily ~4:30pm ET |
| On-demand | `POST /api/v1/data_ingestion/trigger` | User-initiated |
| Gap fill | Triggered by daily flow if gap detected | As needed |

### Output

A successful run produces:
- `OHLCVBar` rows inserted (TimescaleDB hypertable, partition column `bar_date`)
- `MacroObservation` rows inserted (TimescaleDB hypertable, partition column `observed_date`)
- `IngestRun` row recording timing, source-by-source success/failure counts, failed tickers, alerts raised

### Frontend Surfaces

Under `features/monitoring/` (data ingestion doesn't get its own dashboard page; it's an infra layer surfaced through monitoring):
- Read-only status panel on the Model Health Dashboard: "Last successful ingest: 2026-05-28 4:32pm ET. 0 failed tickers."

### Tables

```sql
ohlcv_bars(
  ticker_id FK tickers.id,
  bar_date DATE NOT NULL,
  open NUMERIC(18,6) NOT NULL,
  high NUMERIC(18,6) NOT NULL,
  low NUMERIC(18,6) NOT NULL,
  close NUMERIC(18,6) NOT NULL,
  adjusted_close NUMERIC(18,6),
  volume BIGINT NOT NULL,
  source TEXT NOT NULL,                  -- 'yfinance' | 'alpaca' | 'stooq'
  ingest_run_id FK ingest_runs.id,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (ticker_id, bar_date)
)
-- TimescaleDB hypertable on bar_date
-- index on (ticker_id, bar_date DESC) for latest-N queries

macro_observations(
  series_name TEXT NOT NULL,             -- 'fed_funds_rate', 'cpi', etc.
  observed_date DATE NOT NULL,
  value NUMERIC(18,6) NOT NULL,
  source TEXT DEFAULT 'fred',
  is_forward_filled BOOLEAN DEFAULT false,
  ingest_run_id FK ingest_runs.id,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (series_name, observed_date)
)
-- TimescaleDB hypertable on observed_date

ingest_runs(
  id UUID PK,
  triggered_by ENUM('cold_start','daily_scheduled','on_demand','gap_fill'),
  triggered_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ NULL,
  status ENUM('running','succeeded','partial','failed'),
  ohlcv_rows_inserted INT DEFAULT 0,
  macro_rows_inserted INT DEFAULT 0,
  failed_tickers TEXT[] DEFAULT '{}',
  stale_macro BOOLEAN DEFAULT false,
  error_summary TEXT NULL,
  metadata JSONB DEFAULT '{}'
)
-- index on (triggered_at DESC) for "latest runs"
```

---

## 5. Feature 4 — Feature Engineering (Blocks A2 + A3)

> **Spec reference**: Blocks A2 (Feature Matrix Constructor) and A3 (Feature Tensor Preparation & 4-Horizon Normalization). This feature implements `mbi.features.*` and `mbi.models.data.*` from the spec.

### The 31-Dimensional Contract

Every ticker, every trading day, produces a row in `feature_matrix` with exactly **31 columns** beyond the index:

- **5 raw**: `open`, `high`, `low`, `close`, `volume` (untouched copies from Block A1)
- **19 technical** (TA-Lib + pandas): `returns_{1d,5d,10d,20d}`, `rsi_14`, `macd`, `macd_signal`, `macd_hist`, `bb_{upper,middle,lower}`, `bb_width`, `atr_14`, `volatility_20d`, `volume_z_score`, `sma_{50,200}`, `price_to_sma{50,200}`
- **7 macro**: `fed_funds_rate`, `cpi`, `unemployment`, `gdp`, `yield_spread_10y_2y`, `vix`, `high_yield_spread`

The exact list, calculation, and order is locked in `features/feature_engineering/shared/feature_schema.py`. Any change requires a documented architectural deviation.

### Sub-component Map

| Sub-feature | Spec class | Purpose |
|---|---|---|
| `technical/equity_engineer.py` | `EquityFeatureEngineer` | Compute the 19 technical features per ticker, vectorized via TA-Lib |
| `alignment/macro_merger.py` | `MacroMerger` | Left-join macro DataFrame onto each ticker's feature DataFrame |
| `tensor_prep/target_generator.py` | `TargetGenerator` | Compute T+1, T+5, T+10, T+15 forward returns (continuous, per locked decision) |
| `tensor_prep/feature_scaler.py` | `FeatureScaler` | Rolling 252-day Z-score per feature per ticker, never on targets |
| `tensor_prep/dataset.py` | `TimeSeriesDataset` | PyTorch `Dataset` yielding `(X: [252, 31], y: [4])` tensors |

### Calculation Rules (locked per spec a2.4)

- **Vectorized only.** No `for` loops over rows. TA-Lib for indicator math; pandas for ratios and rolling stats.
- **TA-Lib is primary; `pandas-ta` is the fallback** if the C library can't be installed in a given environment.
- **No target shifting in Block A2.** Targets are computed in Block A3 (`TargetGenerator`).

### The Burn-in Period

A 200-day SMA needs 200 prior bars before it produces a non-NaN value. The orchestrator drops the first ~200 rows from each ticker's feature matrix after all calculations finish. This is intentional and documented; the dropped rows are not silently consumed.

### Lookahead-Bias Protections

| Protection | Mechanism |
|---|---|
| No future data in features | All TA-Lib calls use trailing-window calculations only. Asserted via test fixtures. |
| Targets isolated from features | `FeatureScaler` operates exclusively on the 31 input columns. Targets pass through untouched. |
| Rolling Z-score normalization | Use only the trailing 252 days available at time `t`: `z_t = (x_t - mean(x_{t-252:t})) / std(x_{t-252:t})`. The same trailing-window logic applies to macro features. |
| Per-ticker scaling | Each ticker is normalized in isolation. AAPL's mean/std at time `t` never use MSFT data. |

### Targets (Locked Decision: Continuous Regression)

Per Decision #6 in the brainstorming ledger, targets are **continuous percentage returns**, not binary labels:

```python
# Computed by TargetGenerator
y_T1  = (close.shift(-1)  - close) / close
y_T5  = (close.shift(-5)  - close) / close
y_T10 = (close.shift(-10) - close) / close
y_T15 = (close.shift(-15) - close) / close
```

The last 15 rows of each ticker's DataFrame are dropped (the future hasn't happened yet).

### Tensor Shape Contract

- Input `X` to LSTM and TFT: `[batch_size, 252, 31]` — `(sequence_length, num_features)`.
- Target `y`: `[batch_size, 4]` — continuous returns for `(T+1, T+5, T+10, T+15)`.

### Storage Strategy

The 31-column `feature_matrix` is materialized in TimescaleDB. **Why store, not compute on-the-fly?**

- Daily inference and weekly retrain both need the same features. Computing twice wastes compute and risks drift.
- Storing makes the `feature_inspect` endpoint (debugging power-user view) trivially fast.
- TimescaleDB hypertables on `bar_date` keep storage cheap and queries fast.

The tensor windowing (`TimeSeriesDataset`) is computed *on-demand* in memory at training/inference time from the materialized feature matrix — windows aren't stored.

### Trigger Modes

| Mode | Trigger | Frequency |
|---|---|---|
| Backfill | After cold-start ingest | Once |
| Daily increment | Prefect flow `daily_data_refresh.py` (follows ingestion) | Daily |
| On-demand | `POST /api/v1/feature_engineering/trigger` | User-initiated |
| Forced recompute | When `feature_schema.py` changes | Manual |

### Frontend Surfaces

- `/features/inspect?ticker=AAPL&date=2026-05-28` — power-user view: shows all 31 normalized + raw feature values for one ticker on one day. Useful for debugging.
- The Feature Engineering layer is otherwise invisible to the user; it's pipeline infrastructure.

### Tables

```sql
feature_matrix(
  ticker_id FK tickers.id,
  bar_date DATE NOT NULL,
  -- 5 raw
  open NUMERIC(18,6), high NUMERIC(18,6), low NUMERIC(18,6),
  close NUMERIC(18,6), volume BIGINT,
  -- 19 technical
  returns_1d NUMERIC(18,8), returns_5d NUMERIC(18,8),
  returns_10d NUMERIC(18,8), returns_20d NUMERIC(18,8),
  rsi_14 NUMERIC(18,6),
  macd NUMERIC(18,8), macd_signal NUMERIC(18,8), macd_hist NUMERIC(18,8),
  bb_upper NUMERIC(18,6), bb_middle NUMERIC(18,6), bb_lower NUMERIC(18,6),
  bb_width NUMERIC(18,8),
  atr_14 NUMERIC(18,6),
  volatility_20d NUMERIC(18,8),
  volume_z_score NUMERIC(18,8),
  sma_50 NUMERIC(18,6), sma_200 NUMERIC(18,6),
  price_to_sma50 NUMERIC(18,8), price_to_sma200 NUMERIC(18,8),
  -- 7 macro (joined-in)
  fed_funds_rate NUMERIC(18,6), cpi NUMERIC(18,6), unemployment NUMERIC(18,6),
  gdp NUMERIC(18,6), yield_spread_10y_2y NUMERIC(18,6),
  vix NUMERIC(18,6), high_yield_spread NUMERIC(18,6),
  -- 4 future-return targets (stored for training; null until horizon resolves)
  target_t1 NUMERIC(18,8) NULL,
  target_t5 NUMERIC(18,8) NULL,
  target_t10 NUMERIC(18,8) NULL,
  target_t15 NUMERIC(18,8) NULL,
  -- metadata
  feature_schema_version TEXT NOT NULL,   -- e.g., "v1.0" — bump on schema change
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (ticker_id, bar_date, feature_schema_version)
)
-- TimescaleDB hypertable on bar_date
-- index on (ticker_id, bar_date DESC)

normalization_stats(
  -- Snapshot of rolling Z-score parameters (mean/std) per feature per ticker per date.
  -- Lets us replay normalization deterministically in tests and offline analysis.
  ticker_id FK tickers.id,
  bar_date DATE NOT NULL,
  feature_name TEXT NOT NULL,
  rolling_mean NUMERIC(18,8) NOT NULL,
  rolling_std NUMERIC(18,8) NOT NULL,
  PRIMARY KEY (ticker_id, bar_date, feature_name)
)
-- TimescaleDB hypertable on bar_date
```

---

## 6. Feature 5 — ML Models (Blocks A4, A5, A6)

> **Spec reference**: Blocks A4 (LSTM), A5 (TFT Quad-Array), A6 (Ensemble Engine — Regime Blender + Conformal Calibrator). This feature implements `mbi.models.{dl, tft, ensemble, conformal}.*`.

### Model Topology (Locked Decision: 1 Global Ticker-Agnostic LSTM + 4 Asset-Aware TFTs **per Universe**)

For each Universe `U`:

```
                           Universe U (e.g., S&P 500)
                                      │
                ┌─────────────────────┴─────────────────────┐
                ▼                                           ▼
   LSTM_U (ticker-agnostic global model)         TFT_Quad_Array_U (asset-aware)
   - Sees all tickers in U as undifferentiated   - 4 distinct TFTs (one per horizon)
     training data                                - Ticker_id is a static covariate
   - No ticker embedding input                    - QuantileLoss → distribution outputs
   - Output: 4-horizon continuous return point     - Output: 4-horizon quantile distributions
     estimates [T+1, T+5, T+10, T+15]               (median + spread)
                          │                                  │
                          └──────────────┬───────────────────┘
                                         ▼
                              Ensemble (Block A6)
                              - Uncertainty-aware regime blender
                              - Locally-weighted split conformal calibrator
                              - Emits: (calibrated point, lower bound, upper bound) × 4 horizons
```

So **5 model artifacts per universe** (1 LSTM + 4 TFTs). For three v1 universes (S&P 500, Russell 1000, Russell 2000): **15 models total.**

### Sub-component Map

| Sub-feature | Spec class | Purpose |
|---|---|---|
| `lstm/architecture.py` | `LSTMMathEngine` | nn.Module: Bi-LSTM 3×128 + 8-head attention + linear head (no Sigmoid; Huber-loss target) |
| `lstm/trainer.py` | `LSTMTrainer` | Walk-forward 3-way split, AdamW, HuberLoss, ReduceLROnPlateau, early stopping |
| `lstm/inference.py` | (helper) | Forward pass on a batch of 252×31 tensors → 4 continuous returns |
| `tft/architecture.py` | `TemporalFusionQuadArray` | 4 × pytorch-forecasting TFTs, one per horizon, with ticker as static categorical covariate |
| `tft/trainer.py` | (orchestrator) | 4 × `pytorch-lightning` Trainer instances, QuantileLoss, parallelizable on GPU |
| `tft/inference.py` | (helper) | Returns full quantile distributions, not point estimates |
| `ensemble/blender.py` | `RegimeBlender` | Uncertainty-weighted blend (LSTM point + TFT median + TFT spread) |
| `ensemble/orchestrator.py` | `EnsembleOrchestrator` | Coordinates blender + conformal; emits the final 4-horizon vector |
| `conformal/calibrator.py` | `ConformalCalibrator` | Locally-weighted split conformal prediction; replaces the spec's `ProbabilityCalibrator` |
| `conformal/coverage_tracker.py` | (new) | Per-retrain realized-coverage check |

### LSTM Architecture (per spec a4.2, with locked deviations)

```python
class LSTMMathEngine(nn.Module):
    def __init__(self):
        self.lstm = nn.LSTM(
            input_size=31, hidden_size=128, num_layers=3,
            batch_first=True, bidirectional=True
        )
        # Bidirectional → output dim = 256
        self.attention = nn.MultiheadAttention(
            embed_dim=256, num_heads=8, batch_first=True
        )
        self.head = nn.Sequential(
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 4),
            # NO Sigmoid (locked deviation from spec — see §14)
        )
```

Output shape: `[Batch, 4]`. Unbounded ℝ⁴ — 4 predicted continuous returns.

### TFT Architecture (per spec a5.3)

- 4 independent `TemporalFusionTransformer` objects from `pytorch_forecasting`.
- Each trained with `QuantileLoss(quantiles=[0.1, 0.5, 0.9])`.
- Static categorical covariates: **`ticker_id`** (the asset-aware part).
- Time-varying knowns: macro features (`fed_funds_rate`, `cpi`, etc.).
- Time-varying unknowns: technical features (`rsi_14`, `macd`, etc.).
- Output per horizon: `{q10, q50, q90}` → distribution.

### Loss Functions (Locked Deviation)

| Block | Spec | Locked |
|---|---|---|
| LSTM | `nn.BCELoss` (incoherent — see §14) | **`nn.HuberLoss`** (smooth L1; robust to fat-tailed returns) |
| TFT | `QuantileLoss` | `QuantileLoss` (unchanged) |

### Walk-Forward 3-Way Split (Locked Decision)

Within each rolling 2-year training window:

| Portion | Span | Purpose |
|---|---|---|
| **Train** | First 70% chronologically | Fits LSTM and TFT model weights |
| **Calibration** | Next 15% chronologically | Computes conformal non-conformity scores; never seen by the model during weight updates |
| **Validation** | Last 15% chronologically | Early-stopping signal + final held-out metrics |

**Random shuffling is forbidden.** The split is strictly chronological. Weekly retraining slides this window forward by 7 trading days.

### Training Hyperparameters (per spec a4.3)

| Param | Value |
|---|---|
| Optimizer | AdamW(lr=1e-3, weight_decay=1e-4) |
| LR scheduler | ReduceLROnPlateau(mode='min', patience=5, factor=0.5) |
| Early stopping | Halt after 10 consecutive epochs of no val-loss improvement; restore best weights |
| Max epochs | 100 |
| Batch size | 256 (LSTM); pytorch-forecasting's `TimeSeriesDataSet` chooses for TFT |

### Ensemble Blending (Locked Deviation From Spec a6.2)

The spec hardcodes 60/40 LSTM/TFT weights. **We replace this with uncertainty-aware weighting** that uses TFT's quantile spread as a regime signal:

```python
def blend_horizon(lstm_pred, tft_q10, tft_q50, tft_q90, base_lstm_w=0.60):
    # TFT spread is a model-implied volatility — wider spread = more uncertain
    tft_spread = tft_q90 - tft_q10
    # Normalize spread relative to a rolling baseline
    spread_z = normalize_against_history(tft_spread)
    # When TFT is more uncertain, lean on LSTM
    lstm_w = clip(base_lstm_w + 0.10 * spread_z, 0.40, 0.80)
    tft_w = 1.0 - lstm_w
    return (lstm_pred * lstm_w) + (tft_q50 * tft_w)
```

`base_lstm_w` is config-tunable. The blender is symmetric across horizons — same formula for T+1, T+5, T+10, T+15.

### Conformal Calibration (Locked Decision: Locally-Weighted Split Conformal)

Custom lightweight implementation in `conformal/calibrator.py` (~120 lines of NumPy). Steps per retrain:

1. **Fit blended model** on the 70% train slice.
2. **Generate predictions** on the 15% calibration slice.
3. **Compute non-conformity scores**, locally weighted by predicted residual magnitude:
   ```python
   s_i = |y_true_i - y_pred_i| / (residual_predictor(x_i) + epsilon)
   ```
   `residual_predictor` is a small MLP fit alongside, predicting expected absolute residual from features.
4. **Take the (1−α) quantile** of `{s_i}` per horizon. Default α=0.10 (90% coverage target).
5. **Store quantile** in the `ModelArtifact`. At inference:
   ```python
   q = stored_quantile
   r_hat = residual_predictor(x_new)
   interval = [y_pred - q * r_hat,  y_pred + q * r_hat]
   ```

This is **locally-weighted** because the interval width adapts to local volatility — wider during VIX spikes, narrower in calm regimes.

### Conviction Score (Locked: Derivation A — Risk-Adjusted Magnitude)

Per horizon, the score is derived as:

```python
def conviction_score(y_pred, tft_q10, tft_q90, conformal_width):
    # Model-implied σ (use TFT spread as the primary uncertainty signal)
    sigma = (tft_q90 - tft_q10) / 2.563     # convert 10-90 spread to ~1σ-equivalent
    # Risk-adjusted return
    z = y_pred / (sigma + 1e-9)
    # Center at 50 (neutral), scale to roughly [0, 100]
    raw_score = z * 25 + 50
    # Clip
    return clip(raw_score, 0, 100)
```

Examples (intuition):
- `y_pred = +2%, sigma = 1.5%` → `z = 1.33` → `score = 83.3` (strong bullish)
- `y_pred = +0.5%, sigma = 2.5%` → `z = 0.20` → `score = 55.0` (mild bullish, low confidence)
- `y_pred = -1.5%, sigma = 1.8%` → `z = -0.83` → `score = 29.1` (bearish)

The four horizon scores are stored alongside the four point estimates and intervals.

### Artifact Storage

Each retrain produces one `ModelArtifact` row per `(universe, model_role)`:
- `universe_id`
- `model_role` ENUM: `'lstm'`, `'tft_t1'`, `'tft_t5'`, `'tft_t10'`, `'tft_t15'`, `'conformal'`, `'residual_predictor'`
- `artifact_path` (local FS path; later S3 key)
- `training_run_id` (FK to `TrainingRun`)
- `metadata` JSONB (hyperparams snapshot, validation metrics)
- `is_active` BOOLEAN (only one active artifact per `(universe, model_role)` at a time)

Old artifacts are **kept** by default (cheap; useful for rollback and A/B). A retention reaper drops artifacts > 6 months old via a daily flow.

### Frontend Surfaces

Under `features/model_health/`:
- `/model-health/{universe_id}` — current model card: training-run timeline, validation loss curves, conformal coverage history
- `/model-health/{universe_id}/training-history` — chronological list of training runs with metrics
- `/model-health/{universe_id}/artifacts` — list of stored artifacts with rollback button

### Tables

```sql
training_runs(
  id UUID PK,
  universe_id FK universes.id,
  triggered_by ENUM('weekly_scheduled','on_demand','cold_start'),
  started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ NULL,
  status ENUM('running','succeeded','failed'),
  train_window_start DATE, train_window_end DATE,
  calibration_window_start DATE, calibration_window_end DATE,
  validation_window_start DATE, validation_window_end DATE,
  num_tickers INT, num_training_samples BIGINT,
  hyperparams_snapshot JSONB,
  validation_metrics JSONB,
  error_summary TEXT NULL,
  metadata JSONB DEFAULT '{}'
)
-- index on (universe_id, started_at DESC)

model_artifacts(
  id UUID PK,
  universe_id FK universes.id,
  training_run_id FK training_runs.id,
  model_role ENUM('lstm','tft_t1','tft_t5','tft_t10','tft_t15','conformal','residual_predictor'),
  artifact_path TEXT NOT NULL,
  size_bytes BIGINT,
  is_active BOOLEAN DEFAULT false,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  archived_at TIMESTAMPTZ NULL
)
-- UNIQUE partial index: (universe_id, model_role) WHERE is_active = true
-- index on (universe_id, model_role, created_at DESC)

inference_runs(
  id UUID PK,
  universe_id FK universes.id,
  triggered_by ENUM('daily_scheduled','on_demand'),
  inference_date DATE NOT NULL,    -- date of close prices used as features
  started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ NULL,
  status ENUM('running','succeeded','failed'),
  artifact_ids JSONB NOT NULL,     -- which 7 artifacts were used
  num_tickers_scored INT,
  error_summary TEXT NULL
)

predictions(
  id UUID PK,
  inference_run_id FK inference_runs.id,
  ticker_id FK tickers.id,
  universe_id FK universes.id,
  inference_date DATE NOT NULL,
  -- per horizon: blended point, conformal interval, conviction score
  pred_t1 NUMERIC(18,8), pred_lo_t1 NUMERIC(18,8), pred_hi_t1 NUMERIC(18,8), conviction_t1 NUMERIC(6,2),
  pred_t5 NUMERIC(18,8), pred_lo_t5 NUMERIC(18,8), pred_hi_t5 NUMERIC(18,8), conviction_t5 NUMERIC(6,2),
  pred_t10 NUMERIC(18,8), pred_lo_t10 NUMERIC(18,8), pred_hi_t10 NUMERIC(18,8), conviction_t10 NUMERIC(6,2),
  pred_t15 NUMERIC(18,8), pred_lo_t15 NUMERIC(18,8), pred_hi_t15 NUMERIC(18,8), conviction_t15 NUMERIC(6,2),
  -- raw component outputs for debugging
  lstm_outputs NUMERIC[] NOT NULL,    -- length 4
  tft_q10 NUMERIC[] NOT NULL,         -- length 4
  tft_q50 NUMERIC[] NOT NULL,         -- length 4
  tft_q90 NUMERIC[] NOT NULL,         -- length 4
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(ticker_id, universe_id, inference_date)
)
-- TimescaleDB hypertable on inference_date
-- index on (universe_id, inference_date DESC)
-- index on (ticker_id, inference_date DESC)
```

---

## 7. Feature 6 — Backtesting (Block A7)

> **Spec reference**: Block A7 (The 4-Strategy Vectorized Backtester). Implements `mbi.models.backtest.*`.

### Purpose

Block A7 is the **empirical proving ground** that sits *before* a prediction becomes a tradable conviction ticket. Even if the ML models give a strong signal on ticker T, we don't surface it unless T historically exhibits exploitable edge across at least 2 of the 4 paradigm strategies. This is the "have we ever made money on this stock under any of these models?" check.

### The 4 Strategies (Locked per Spec a7.3)

Implemented as separate classes inheriting from `BaseStrategy` (ABC in `backtesting/shared/base.py`):

| Strategy | Entry | Exit |
|---|---|---|
| **MeanReversion** | `close < bb_lower` | `close > bb_middle` |
| **MomentumCross** | `(sma_50 > sma_200) & (sma_50.shift(1) <= sma_200.shift(1))` | Inverse crossover |
| **VolatilityBreakout** | `(atr_14 > 1.25 × atr_14.rolling(14).mean()) & (close > close.rolling(20).max().shift(1))` | `close < 0.95 × close.rolling(20).max()` |
| **StatArb** | `scipy.stats.linregress` rolling 60-day OLS of asset vs. SPY; entry when residual < −2σ | Exit when residual > −0.5σ |

`BaseStrategy.generate_signals(df)` returns `(entries: pd.Series[bool], exits: pd.Series[bool])`.

### Vectorbt Execution Engine (per Spec a7.4)

```python
import vectorbt as vbt
portfolio = vbt.Portfolio.from_signals(
    close=df['close'],
    entries=entries, exits=exits,
    init_cash=100_000.0,
    fees=0.001,                # 10 bps slippage/fee
    freq='1D'
)
```

For each strategy run, we extract exactly **6 metrics**:

| Metric | Source |
|---|---|
| `sharpe_ratio` | `portfolio.sharpe_ratio(risk_free=0.045)` |
| `max_drawdown` | `portfolio.max_drawdown()` |
| `total_return` | `portfolio.total_return()` |
| `win_rate` | `portfolio.trades.win_rate()` |
| `profit_factor` | Gross profits / gross losses |
| `total_trades` | `portfolio.trades.count()` |

### Backtest Period

- Default: **5 years rolling window** ending on the inference date.
- Configurable per `BacktestRun` (min 1 year, max all available history).
- Weekly retrain triggers a fresh backtest run per universe.

### Filter Pass Criteria (used by Block A8)

A ticker is said to **pass strategy S** when:
- `sharpe_ratio[S] > 1.5`
- AND `total_trades[S] >= 10` (minimum sample size; not in spec but added to avoid spurious tiny-N "passes" — flagged as a justifiable addition)
- AND `max_drawdown[S] > -0.40` (don't promote tickers that historically blew up)

A ticker is **filter-eligible** if it passes **≥ 2 of the 4 strategies**.

### Trigger Modes

| Mode | Trigger | Frequency |
|---|---|---|
| Weekly all-universe backtest | Prefect flow `weekly_backtest.py` | Sun nights |
| On-demand single-ticker | `POST /api/v1/backtests/trigger?ticker_id=...&universe_id=...` | User-initiated |

### Frontend Surfaces

Under `features/backtesting/`:
- `/backtests/{universe_id}` — explorer: table of all tickers in the universe with strategy-pass badges
- `/backtests/{universe_id}/{ticker_id}` — per-ticker detail: equity curves for each of the 4 strategies, drawdown chart, trade list

### Tables

```sql
backtest_runs(
  id UUID PK,
  universe_id FK universes.id,
  triggered_by ENUM('weekly_scheduled','on_demand'),
  backtest_period_start DATE, backtest_period_end DATE,
  started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ NULL,
  status ENUM('running','succeeded','failed'),
  num_tickers INT, num_strategies INT DEFAULT 4,
  metadata JSONB DEFAULT '{}'
)

backtest_metrics(
  id UUID PK,
  backtest_run_id FK backtest_runs.id,
  ticker_id FK tickers.id,
  strategy_name ENUM('mean_reversion','momentum_cross','volatility_breakout','stat_arb'),
  sharpe_ratio NUMERIC(10,4),
  max_drawdown NUMERIC(10,6),
  total_return NUMERIC(10,6),
  win_rate NUMERIC(6,4),
  profit_factor NUMERIC(10,4),
  total_trades INT,
  passed BOOLEAN GENERATED ALWAYS AS (
    sharpe_ratio > 1.5 AND total_trades >= 10 AND max_drawdown > -0.40
  ) STORED,
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(backtest_run_id, ticker_id, strategy_name)
)
-- index on (ticker_id, strategy_name, computed_at DESC)
-- index on (backtest_run_id, passed) for filter-gate queries
```

---

## 8. Feature 7 — Conviction Tickets (Block A8 + Scoring)

> **Spec reference**: Block A8 (Filter Gate — referenced but not detailed in the source spec) + the "Conviction Ticket" artifact from the whiteboard photos.

### What a Conviction Ticket Is

The end-product of Pipeline A. A row that says: *"On 2026-05-28, for ticker AAPL in universe S&P 500, our models predict a positive move with conviction score 76.4 over the T+5 horizon. It passed 3 of 4 backtests. The 90% conformal interval is [+0.5%, +3.1%]. Status: TRADABLE."*

### The Filter Gate (Block A8 — Locked Criteria)

For each `(ticker, universe, horizon)` triple from today's inference, the filter passes when **all** of the following hold:

| Criterion | Threshold |
|---|---|
| `conviction_score` | `> 67` |
| Predicted return | `> 0` (long-only filter for v1) |
| Backtest pass count | `≥ 2 of 4 strategies` (per Block A7 filter logic) |
| Conformal interval width | `< W_max` (default: 90th percentile of widths from the calibration set) |

`W_max` is config-tunable per universe. The default keeps the top ~90% of intervals (rejecting only the most uncertain predictions).

### Multi-Horizon Tickets

A single inference run can produce up to **4 tickets per ticker** (one per horizon T+1, T+5, T+10, T+15). The filter is applied independently per horizon. If only T+5 passes for AAPL, we emit one T+5 ticket — not four.

### Ticket Status Lifecycle

```
   TRADABLE  ── (no action) ──►   EXPIRED  (when horizon resolution day passes)
       │
       │ user marks
       ▼
   REVIEWED  (user has seen and considered it)
       │
       │ user marks (optional, manual paper-trading bookkeeping)
       ▼
   ACTIONED   (user took a position based on this ticket)
       │
       │ (horizon resolves)
       ▼
   RESOLVED  (we record the actual return for outcome tracking)
```

Status transitions are user-driven from the frontend; the daily Prefect flow handles `TRADABLE → EXPIRED` and `ACTIONED → RESOLVED`.

### Ticket Output Shape (Frontend-Visible)

```json
{
  "id": "ct_abc123...",
  "inference_date": "2026-05-28",
  "ticker": { "id": "...", "symbol": "AAPL", "name": "Apple Inc." },
  "universe": { "id": "...", "name": "sp500", "display_name": "S&P 500" },
  "horizon": "T+5",
  "direction": "LONG",
  "predicted_return": 0.0184,
  "conviction_score": 76.4,
  "conformal_interval": { "low": 0.0053, "high": 0.0315, "alpha": 0.10 },
  "backtest_passes": 3,
  "backtest_pass_strategies": ["mean_reversion", "momentum_cross", "stat_arb"],
  "status": "TRADABLE",
  "resolution_date": "2026-06-04",
  "actual_return": null,             // populated when resolved
  "outcome": null,                    // 'win' | 'loss' | 'flat' when resolved
  "created_at": "2026-05-28T20:45:12Z",
  "expires_at": "2026-06-04T20:00:00Z"
}
```

### Conviction Score Formula (Reiterated — Derivation A)

Computed in `conviction_tickets/scoring/risk_adjusted.py`:

```python
def compute_conviction(y_pred, tft_q10, tft_q90):
    sigma = (tft_q90 - tft_q10) / 2.563
    z = y_pred / (sigma + 1e-9)
    return clip(z * 25 + 50, 0, 100)
```

### Outcome Resolution

A daily Prefect flow runs after market close. For each ticket where `resolution_date == today`:
1. Look up the actual close price on `resolution_date` from `ohlcv_bars`.
2. Compute `actual_return = (close[resolution_date] / close[inference_date]) - 1`.
3. Mark `outcome = 'win'` if `(actual_return > 0 AND direction == LONG)`, `'loss'` if opposite-signed, `'flat'` if `|actual_return| < 0.001`.
4. Update `status = 'RESOLVED'` if previously `TRADABLE` or `REVIEWED`; preserve `ACTIONED` outcomes specifically.

### Frontend Surfaces

Under `features/conviction_tickets/`:
- `/tickets` — **The Inbox.** All currently TRADABLE tickets across all universes. Filters: universe, horizon, conviction range, backtest-pass-count, conformal-width range. Sort: conviction desc by default.
- `/tickets/{id}` — Detail view: full breakdown of ensemble math, conformal interval visualization, backtest pass-by-strategy table, feature snapshot link to `/features/inspect`, action buttons (Mark Reviewed / Actioned)
- `/tickets/history` — Chronological list with outcome filters (won/lost/flat/pending)
- `/tickets/export.csv` — Export current filtered set as CSV (capped 10K rows)

### Tables

```sql
conviction_tickets(
  id UUID PK,
  inference_run_id FK inference_runs.id,
  ticker_id FK tickers.id,
  universe_id FK universes.id,
  inference_date DATE NOT NULL,
  horizon ENUM('T1','T5','T10','T15'),
  direction ENUM('LONG'),                  -- 'SHORT' reserved for v2
  predicted_return NUMERIC(18,8) NOT NULL,
  conviction_score NUMERIC(6,2) NOT NULL,
  conformal_lower NUMERIC(18,8) NOT NULL,
  conformal_upper NUMERIC(18,8) NOT NULL,
  conformal_alpha NUMERIC(4,2) DEFAULT 0.10,
  backtest_run_id FK backtest_runs.id,
  backtest_passes INT NOT NULL,
  backtest_pass_strategies TEXT[] NOT NULL,
  status ENUM('TRADABLE','REVIEWED','ACTIONED','RESOLVED','EXPIRED') DEFAULT 'TRADABLE',
  resolution_date DATE NOT NULL,
  actual_return NUMERIC(18,8) NULL,
  outcome ENUM('win','loss','flat') NULL,
  created_by_user_id FK users.id NULL,   -- NULL = system-generated
  user_notes TEXT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(inference_run_id, ticker_id, horizon)
)
-- index on (universe_id, status, conviction_score DESC) — for inbox queries
-- index on (resolution_date, status) — for outcome-resolution sweep
-- index on (ticker_id, inference_date DESC)

filter_runs(
  id UUID PK,
  inference_run_id FK inference_runs.id,
  backtest_run_id FK backtest_runs.id,
  started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  num_predictions_evaluated INT,
  num_tickets_emitted INT,
  filter_config JSONB NOT NULL,   -- snapshot of thresholds used
  metadata JSONB DEFAULT '{}'
)
```

---

## 9. Feature 8 — Monitoring & Model Health

### Purpose

The user-facing **Model Health Dashboard** + the system's internal **observability surface**. Tracks whether the engine is behaving correctly over time and surfaces issues before they become silent failures.

### Tracked Signals

| Signal | What it tells you |
|---|---|
| **Conformal coverage** | Realized vs. nominal coverage of conformal intervals on resolved tickets. Target: 90% (for α=0.10). Sustained drop below 80% = model is overconfident → red alert. |
| **Train/val loss curves** | Per training run, per universe. Show convergence patterns and detect overfitting (train going down while val plateaus or rises). |
| **Conviction-vs-outcome correlation** | Among RESOLVED tickets in a rolling window, is high conviction actually predictive? Spearman rank correlation of `conviction_score` vs. `actual_return` should be > 0.2 sustained. |
| **Backtest pass-rate drift** | What fraction of universe tickers pass ≥2 strategies? If this trends down monthly, market regime may have shifted. |
| **Pipeline run success rate** | Fraction of daily flows that succeed without alerts. Should be > 95%. |
| **Data freshness** | Time since last successful ingest per universe. Alert if > 36 hours. |
| **Feature drift** | KL divergence between current 252-day feature distribution and the training distribution. Alert if drift > threshold per feature. |

### Per-Universe Model Card

For each universe:
- Last training run timestamp + status
- Current active artifacts (5: 1 LSTM + 4 TFTs + 1 conformal calibrator)
- Validation metrics: MAE per horizon, MSE per horizon, Pearson correlation of pred vs. actual on val set
- Conformal coverage last 30/90 days
- Most-recent 10 TRADABLE tickets

### Frontend Surfaces

Under `features/monitoring/`:
- `/health` — overview dashboard across all universes
- `/health/{universe_id}` — per-universe model card
- `/health/coverage` — conformal coverage history chart, per universe per horizon
- `/health/drift` — feature drift indicators
- `/health/runs` — list of recent pipeline runs (links out to Prefect UI for deep dives)

### Alert Routing

For v1, alerts log to loguru (visible via `tail -f` on the backend). The `team_alerts`-equivalent table — `system_alerts` — stores structured alert records. Future hooks: Slack webhook, email digest.

### Tables

```sql
coverage_metrics(
  id UUID PK,
  universe_id FK universes.id,
  horizon ENUM('T1','T5','T10','T15'),
  measurement_date DATE NOT NULL,
  window_size INT NOT NULL,         -- e.g., 30 days
  realized_coverage NUMERIC(6,4),   -- e.g., 0.8814 = 88.14%
  nominal_coverage NUMERIC(4,2),    -- e.g., 0.90
  num_tickets_resolved INT,
  is_alert BOOLEAN DEFAULT false,
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(universe_id, horizon, measurement_date, window_size)
)

feature_drift_metrics(
  id UUID PK,
  universe_id FK universes.id,
  feature_name TEXT NOT NULL,
  measurement_date DATE NOT NULL,
  kl_divergence NUMERIC(18,8),
  threshold_breached BOOLEAN DEFAULT false,
  computed_at TIMESTAMPTZ DEFAULT NOW()
)

system_alerts(
  id UUID PK,
  severity ENUM('info','warning','critical'),
  code TEXT NOT NULL,               -- e.g., 'COVERAGE_BREACH', 'INGEST_STALE'
  universe_id FK universes.id NULL,
  message TEXT NOT NULL,
  context JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ NULL,
  resolved_at TIMESTAMPTZ NULL
)
-- index on (resolved_at, severity) WHERE resolved_at IS NULL
```

---

## 10. Feature 9 — Orchestration (Prefect Flows)

### Why Prefect (Locked Decision)

Prefect 3 self-hosted, sharing the same Postgres. Provides:
- Visual flow dashboard (we link to it from the monitoring UI rather than rebuild it)
- Task-level retries with backoff (in addition to in-code `tenacity` retries)
- Schedule management (daily after close, weekly on Sundays)
- Run history and audit trail

### Flow Inventory

| Flow | Trigger | Composition |
|---|---|---|
| `daily_data_refresh.py` | Cron: weekdays 4:20pm ET | Ingest → Feature engineering increment |
| `daily_inference.py` | Cron: weekdays 5:30pm ET (after data refresh) | Inference per universe → Filter → Emit tickets |
| `weekly_retrain.py` | Cron: Sundays 6am ET | Walk-forward 3-way split → Train LSTM → Train TFT Quad → Fit conformal → Activate new artifacts → Archive old |
| `weekly_backtest.py` | Cron: Sundays 4am ET (before retrain) | 5-year backtest of all 4 strategies per universe |
| `conformal_coverage_check.py` | Cron: daily 11pm ET | Compute realized coverage on resolved tickets, write `coverage_metrics`, raise alert if breached |
| `outcome_resolution.py` | Cron: weekdays 5:00pm ET | Resolve TRADABLE/ACTIONED tickets whose horizon ended today |
| `artifact_retention.py` | Cron: weekly Sundays 11pm ET | Archive ModelArtifacts > 6 months old |

### Flow Composition Pattern

Each flow is a thin Prefect orchestration layer that **calls feature services**. No business logic lives in the flow itself.

```python
# orchestration/flows/daily_inference.py
from prefect import flow, task
from backend.features.universes.service import list_active_universes
from backend.features.ml_models.service import run_inference
from backend.features.conviction_tickets.filter.gate import apply_filter

@task(retries=3, retry_delay_seconds=60)
def infer_for_universe(universe_id: UUID) -> InferenceRun:
    return run_inference(universe_id, inference_date=today())

@task
def emit_tickets(inference_run: InferenceRun) -> FilterRun:
    return apply_filter(inference_run)

@flow(name="daily_inference")
def daily_inference_flow():
    universes = list_active_universes()
    for u in universes:
        run = infer_for_universe(u.id)
        emit_tickets(run)
```

### Failure Behavior

- Per-task retry (3 attempts, exponential backoff)
- Flow-level alerts: a failed flow writes a `system_alerts` row via the on-failure hook
- No automatic rollback. Failed retrains leave the previous active artifact in place. New artifacts only become `is_active=true` after the entire training pipeline succeeds.

### Frontend Surfaces

- Link out to Prefect UI at `/orchestration` (iframe or external link)
- Recent flow runs summary panel on the monitoring dashboard

### Tables (Prefect Manages Its Own Schema)

Prefect creates and migrates its own tables in a separate `prefect` schema within the same database. No application-side modeling required.

---

## 11. Cross-cutting Patterns

### Soft-delete Pattern

Applied to: `universes`, `conviction_tickets` (for user-deleted ones), `model_artifacts` (archived not purged).

- `deleted_at TIMESTAMPTZ NULL` column.
- Default queries filter `WHERE deleted_at IS NULL`.
- "Include deleted" toggle removes the filter.
- No 30-day grace period on universes/tickets in v1 (different from Feenix because Pipeline A artifacts are largely append-only and lightly mutated; we don't have the binary-storage cost concern).

### Background Schedulers

Two schedulers run inside the FastAPI process via `lifespan`:

| Scheduler | Interval | Purpose |
|---|---|---|
| **TimescaleDB partition manager** | Monthly | Pre-create next month's `ohlcv_bars`, `feature_matrix`, `predictions` partitions |
| **Session reaper** | Hourly | Delete expired `sessions` rows |

Heavier work (data refresh, retrain, inference) lives in Prefect flows, not in the in-process scheduler.

### Standard API Error Envelope

```json
{
  "error_code": "MACHINE_READABLE_CODE",
  "message": "Human-friendly message",
  "details": { "field": "value", "..." : "..." },
  "request_id": "req_abc..."
}
```

Codes: `UNIVERSE_NOT_FOUND`, `TICKER_NOT_FOUND`, `INSUFFICIENT_DATA`, `MODEL_NOT_TRAINED`, `BACKTEST_FAILED`, `CONFORMAL_NOT_FIT`, etc.

### Roles Enforcement

`requires_role(["admin"])` FastAPI dependency. In v1, every protected endpoint uses `requires_role(["admin"])`. The dependency is shared across features.

### Polling Strategy (Frontend)

TanStack Query `refetchInterval` per surface:
- Ticket inbox: 60s
- Model health: 60s
- Training-run-in-progress detail: 5s
- Pipeline-run list: 30s
- Universe list: on-demand only (manual refresh button)

### Repository Abstraction

Per-feature `repository.py` centralizes data access. Future cache decoration is one place.

### Logging Conventions

- All log output: structured JSON to stdout (loguru formatter).
- Required fields: `ts`, `level`, `request_id`, `user_id` (when applicable), `universe_id` (when applicable), `event`.
- Sensitive values (passwords, JWTs, API keys) never logged.

### Validation Layer

- Pydantic v2 schemas in feature's `schemas.py`.
- 422 responses include full validation error tree.

---

## 12. Master Data Model Summary

```
users ───┬──── sessions
         │
         ├──── universes ──┬── universe_memberships ──── tickers ──┬── ohlcv_bars
         │                 │                                       │
         │                 ├── training_runs ──┬── model_artifacts │
         │                 │                   │                   │
         │                 ├── inference_runs ─┴── predictions ────┤
         │                 │                                       │
         │                 ├── backtest_runs ──── backtest_metrics │
         │                 │                                       │
         │                 ├── conviction_tickets ◄────────────────┘
         │                 │       │
         │                 │       └── filter_runs
         │                 │
         │                 ├── coverage_metrics
         │                 ├── feature_drift_metrics
         │                 └── system_alerts
         │
         └── feature_matrix ◄── (joins on ticker_id + bar_date)
              │
              └── normalization_stats

macro_observations (standalone, joined into feature_matrix by date)

ingest_runs (standalone, FK'd from ohlcv_bars and macro_observations)
```

### Tables by Owning Feature

| Table | Feature | Notes |
|---|---|---|
| `users` | `auth` | Single admin in v1; multi-user-ready |
| `sessions` | `auth` | Refresh-token-backed |
| `universes` | `universes` | Named baskets |
| `tickers` | `universes` | Canonical symbol registry |
| `universe_memberships` | `universes` | Time-aware join |
| `ohlcv_bars` | `data_ingestion` | TimescaleDB hypertable |
| `macro_observations` | `data_ingestion` | TimescaleDB hypertable |
| `ingest_runs` | `data_ingestion` | Audit + alerting |
| `feature_matrix` | `feature_engineering` | TimescaleDB hypertable, 31 cols + 4 targets |
| `normalization_stats` | `feature_engineering` | Rolling Z-score parameters |
| `training_runs` | `ml_models` | Per-universe, per-week typically |
| `model_artifacts` | `ml_models` | 5 active per universe |
| `inference_runs` | `ml_models` | Daily |
| `predictions` | `ml_models` | Per (ticker, universe, inference_date) |
| `backtest_runs` | `backtesting` | Per-universe, weekly |
| `backtest_metrics` | `backtesting` | Per (run, ticker, strategy) |
| `filter_runs` | `conviction_tickets` | Per inference |
| `conviction_tickets` | `conviction_tickets` | The headline output |
| `coverage_metrics` | `monitoring` | Conformal coverage tracking |
| `feature_drift_metrics` | `monitoring` | Per-feature KL divergence |
| `system_alerts` | `monitoring` | Cross-feature alerting |

---

## 13. Repository Architecture

See the directory tree previously approved during brainstorming. Quick recap:

```
mbi-labs/
├── backend/
│   ├── alembic/
│   ├── pyproject.toml (uv)
│   ├── scripts/  (typer CLIs)
│   ├── src/backend/
│   │   ├── main.py
│   │   ├── core/  (db, settings, logging, scheduler, security, artifact_store)
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── universes/
│   │   │   ├── data_ingestion/        # Block A1
│   │   │   ├── feature_engineering/   # Blocks A2 + A3
│   │   │   ├── ml_models/             # Blocks A4 + A5 + A6
│   │   │   ├── backtesting/           # Block A7
│   │   │   ├── conviction_tickets/    # Block A8 + scoring
│   │   │   └── monitoring/
│   │   └── orchestration/             # Prefect flows
│   └── tests/                          # Cross-feature integration
└── frontend/  (Vite + React + TS strict, mirrors feature names)
```

Each feature has: `features.md`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `dependencies.py` (if needed), `router.py`, `endpoints/` directory, `tests/` directory. Sub-features nest the same pattern.

---

## 14. Deviations From the Original Spec

These are explicit, documented departures from the source PDF. Each one was discussed during brainstorming and locked.

| # | Spec Says | We're Doing | Reason |
|---|---|---|---|
| 1 | LSTM head ends in `Sigmoid()` + targets are continuous returns + loss is `BCELoss` | LSTM head ends in `Linear()` (no Sigmoid); targets stay continuous; loss is `HuberLoss` | Original is mathematically incoherent — BCE expects {0,1} labels. Continuous regression with Huber is the principled fix. |
| 2 | TFT outputs run through `Sigmoid(x) = 1/(1+e^(-x))` | TFT outputs are kept as full quantile distributions (q10, q50, q90); Sigmoid removed | Sigmoid on a raw return value (~0.02) gives ~0.505, contributing essentially nothing. Quantile distributions are inherently meaningful. |
| 3 | Ensemble blending is hardcoded 60/40 LSTM/TFT | Uncertainty-aware blending using TFT quantile spread as a regime signal; weights adapt within [0.40, 0.80] | Static weights ignore the model's own uncertainty signal. The change makes "regime-aware weighting" in the spec literal. |
| 4 | `ProbabilityCalibrator` with `IsotonicRegression(out_of_bounds='clip')` | `ConformalCalibrator` with **Locally-Weighted Split Conformal Prediction** (custom NumPy implementation) | Isotonic regression calibrates *binary probabilities*. With continuous regression targets it doesn't apply. Conformal prediction is the correct calibration tool for regression and gives statistical interval coverage guarantees. |
| 5 | Walk-forward is 80/20 train/val | Walk-forward is 70/15/15 train/calibration/validation | Conformal prediction needs a held-out calibration set distinct from validation. The 3-way split is mandatory for the new calibrator. |
| 6 | Filter is `P(move) > 0.67` | Filter is `conviction_score > 67 AND predicted_return > 0 AND backtest_passes >= 2 AND conformal_interval_width < W` | `P(move)` no longer exists once we shifted from binary to regression. The new filter preserves the spirit (conviction threshold + backtest gating) and adds the conformal-width guardrail. |
| 7 | "Conviction Score (0-100)" referenced but not defined | Derivation A: `clip(y_pred / sigma * 25 + 50, 0, 100)` where `sigma = (q90-q10)/2.563` | Required because conviction must be derived from continuous regression outputs. Risk-adjusted magnitude matches the whiteboard semantics ("score: 76.4"). |
| 8 | `ProbabilityCalibrator` stores 4 isotonic models | `ConformalCalibrator` stores: 4 conformal quantiles + 1 residual predictor (small MLP) | Direct consequence of (4). |
| 9 | LSTM `input_size=31` strictly enforced | Same — but only because we explicitly chose a **ticker-agnostic** global LSTM (no ticker embedding extending input dim) | Rule 1 of the manifesto preserved. Ticker-aware behavior is delegated to the TFT, which natively supports static covariates. |
| 10 | Polygon and Alpha Vantage are part of the failover chain | Interface preserved; concrete implementations dropped for v1 in favor of **yfinance + Alpaca + Stooq** (all free) | User scoping decision. Polygon/AlphaVantage can be added later as new `DataFetcher` subclasses without architectural changes. |
| 11 | Block A7 strategy filter uses Sharpe > 1.5 only | Added `total_trades >= 10 AND max_drawdown > -0.40` to avoid spurious passes from tiny-N samples and exclude historical blow-ups | Defensive engineering. Documented and config-tunable. |
| 12 | LSTM `BCELoss` — locked Rule 1 says no "alterations" | We are altering it (see #1) | Rule 1 forbids silent alterations. This one is explicit, documented, and approved during brainstorming. |

All twelve deviations are **architectural decisions explicitly approved by the user during brainstorming**, not "hallucinated optimizations."

---

## 15. Future-Friendly Hooks (deferred from v1)

These are documented so v1 doesn't code itself into corners. None block v1.

| Deferred Feature | When to revisit | What v1 designs for |
|---|---|---|
| **Pipeline B — LLM Agent Swarm + Fusion Engine** | After Pipeline A is producing stable conviction tickets | Conviction tickets table already includes everything Pipeline B will need to consume + fuse with; ML artifacts have a stable interface |
| **Multi-user / team workspaces** | When opening to others | `user_id` foreign keys reserved on every tenant-scoped table; `memberships.role` enum reserved |
| **RL / continuous-learning loop** | After Pipeline A's static weekly retrain proves stable | The whiteboard's "DL weight update / reward signal / RL loop" arrow is a planned Block A9. Inference outputs + outcome resolution data are stored explicitly to feed a future reward signal. |
| **Short positions** | When the system is profitable on longs | `conviction_tickets.direction` enum already supports `SHORT` (just commented out) |
| **Paper-trading sandbox** | After Pipeline B + tickets prove out | This is what TigerBeetle would be added for. Reserved decision. |
| **Real-time / intraday inference** | If trading style demands it | Feature schema would need intraday bars; new fetcher subclass + new normalization window |
| **Cloud deployment (Railway/AWS)** | After local proves stable | MinIO swap point in `core/services/artifact_store.py`; Postgres connection string is env-driven |
| **Polygon.io / Alpha Vantage paid sources** | When yfinance reliability becomes a problem | New `DataFetcher` subclasses; orchestrator wiring is one line |
| **Conformal upgrade: Adaptive Conformal Inference (ACI)** | When weekly walk-forward feels too slow for regime shifts | Current conformal class has an `update_quantile()` hook |
| **TFT with covariate engineering** (sector, market cap, etc.) | When ticker_id alone isn't enough static signal | TFT `static_categoricals` and `static_reals` lists are config-driven |
| **Multi-asset universes** (crypto, FX) | When equities prove out | `tickers.asset_type` enum is extensible |
| **Slack / email alerting** | When v1 monitoring fires too many silent alerts | `system_alerts` table is the alert source-of-truth |
| **Prometheus / OpenTelemetry** | When ops scale demands real metrics | loguru JSON logs are already structured; metric derivation is offline |
| **Model A/B testing** | When you want to test new architectures without risking the daily output | `model_artifacts.is_active` is a partial-unique constraint — easily extended to a "champion / challenger" enum |
| **User-facing notebooks / DSL** | When power users want to define custom strategies | Strategy ABC is clean; a `CustomStrategy(BaseStrategy)` plug-in mechanism is a one-day add |

---

## End of Design Document

All 16 decisions documented in the brainstorming ledger are explicitly approved. All 12 deviations from the source spec are documented and reasoned. Next deliverable: `tech-stack-analysis.md`, then the phased `development-plan.md`.
