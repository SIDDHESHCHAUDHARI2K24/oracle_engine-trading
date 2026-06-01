# Pipeline A — Agent Instructions (Backend)

> **Scope**: Pipeline A — the Deep Learning Math Engine. A self-improving research-grade ML pipeline.
> **Companion docs**: `mbi-pipeline-a-v1-design.md`, `tech-stack-analysis.md`
> **For frontend instructions**: See `agent-instructions/Frontend-Agent-Instructions.md`

---

## 1. Pipeline A Overview

Pipeline A is a self-improving research-grade ML pipeline that:
1. Ingests OHLCV + macroeconomic data across multiple equity universes (Block A1)
2. Engineers a 31-dimensional feature tensor per ticker per day (Blocks A2 + A3)
3. Trains a Bi-LSTM and a Temporal Fusion Transformer Quad-Array per universe (Blocks A4 + A5)
4. Blends ensemble predictions with uncertainty-aware weighting (Block A6)
5. Calibrates with locally-weighted split conformal prediction (Block A6)
6. Validates via four backtest strategies (Block A7)
7. Emits filtered Conviction Tickets for human review (Block A8)
8. Monitors model health, conformal coverage, feature drift (Feature 8)
9. Orchestrates daily/weekly flows via Prefect (Feature 9)

### 9 Features Summary

| # | Feature | Spec Block | Key Artifact |
|---|---|---|---|
| 1 | Auth & User Accounts | — | JWT + session-backed refresh |
| 2 | Universe Management | — | Time-aware ticker baskets |
| 3 | Data Ingestion | A1 | OHLCV + macro in TimescaleDB |
| 4 | Feature Engineering | A2 + A3 | 31-dim feature matrix + 4-horizon targets |
| 5 | ML Models | A4 + A5 + A6 | 1 LSTM + 4 TFTs + conformal per universe |
| 6 | Backtesting | A7 | 4 strategies × 6 metrics, filter gate |
| 7 | Conviction Tickets | A8 | Risk-adjusted score, filter gate, lifecycle |
| 8 | Monitoring & Model Health | — | Coverage, drift, loss curves, alerts |
| 9 | Orchestration | — | 7 Prefect flows on cron schedules |

---

## 2. Locked Architecture Decisions

These decisions were locked during brainstorming and CANNOT be changed without explicit user approval:

### Decision 1: 1 Global Ticker-Agnostic LSTM + 4 Asset-Aware TFTs per Universe

For each Universe U:
- **LSTM_U**: Ticker-agnostic global model. Sees all tickers as undifferentiated. No ticker embedding. Input: [batch, 252, 31]. Output: 4 continuous returns.
- **TFT_Quad_Array_U**: 4 distinct TFTs (one per horizon: T+1, T+5, T+10, T+15). Ticker_id is a static covariate. QuantileLoss → distribution outputs.
- **5 model artifacts per universe**. For 3 v1 universes (S&P 500, Russell 1000, Russell 2000): **15 models total.**

### Decision 2: 31-Dimensional Feature Contract

Every ticker, every trading day, produces exactly 31 columns:
- **5 raw**: open, high, low, close, volume
- **19 technical**: returns_{1d,5d,10d,20d}, rsi_14, macd, macd_signal, macd_hist, bb_{upper,middle,lower}, bb_width, atr_14, volatility_20d, volume_z_score, sma_{50,200}, price_to_sma{50,200}
- **7 macro**: fed_funds_rate, cpi, unemployment, gdp, yield_spread_10y_2y, vix, high_yield_spread

Locked in `features/feature_engineering/shared/feature_schema.py`. Any change requires a documented architectural deviation.

### Decision 3: Walk-Forward 3-Way Split (70/15/15)

Within each rolling 2-year training window:
- **Train**: First 70% chronologically
- **Calibration**: Next 15% (conformal non-conformity scores; never seen during weight updates)
- **Validation**: Last 15% (early-stopping signal + held-out metrics)

**Random shuffling is FORBIDDEN.** Weekly retraining slides window forward by 7 trading days.

### Decision 4: Locally-Weighted Split Conformal Calibration (NOT Isotonic Regression)

Custom lightweight implementation in `conformal/calibrator.py` (~120 lines of NumPy). Steps:
1. Fit blended model on 70% train slice
2. Generate predictions on 15% calibration slice
3. Compute non-conformity scores, locally weighted by predicted residual magnitude
4. Take (1−α) quantile of scores per horizon (default α=0.10, 90% coverage)
5. Store quantile; at inference: interval = [y_pred − q·r_hat, y_pred + q·r_hat]

### Decision 5: Uncertainty-Aware Ensemble Blending (NOT 60/40 Static)

```python
tft_spread = tft_q90 - tft_q10
spread_z = normalize_against_history(tft_spread)
lstm_w = clip(base_lstm_w + 0.10 * spread_z, 0.40, 0.80)
tft_w = 1.0 - lstm_w
blended = (lstm_pred * lstm_w) + (tft_q50 * tft_w)
```

When TFT is more uncertain (wider spread), lean on LSTM. `base_lstm_w` is config-tunable.

### Decision 6: Continuous Regression Targets (NOT Binary Labels)

Targets are continuous percentage returns:
```python
y_T1 = (close.shift(-1) - close) / close
y_T5 = (close.shift(-5) - close) / close
y_T10 = (close.shift(-10) - close) / close
y_T15 = (close.shift(-15) - close) / close
```
Last 15 rows dropped (future hasn't happened yet).

### Decision 7: HuberLoss for LSTM (NOT BCELoss)

Original spec had `nn.BCELoss` — mathematically incoherent with continuous regression targets. **`nn.HuberLoss`** (smooth L1) is robust to fat-tailed returns. TFT uses `QuantileLoss` (unchanged).

### Decision 8: Conviction Score — Risk-Adjusted Magnitude

```python
sigma = (tft_q90 - tft_q10) / 2.563 # 10-90 spread to ~1σ
z = y_pred / (sigma + 1e-9)
score = clip(z * 25 + 50, 0, 100)
```
Centered at 50 (neutral). Strong bullish ≈ 80+, mild bullish ≈ 55, bearish ≈ 30.

### Decision 9: Long-Only Filter for v1

Conviction tickets only emitted for predicted_return > 0. `SHORT` direction enum reserved in schema for v2.

### Decision 10: Filter Gate Criteria (for Conviction Tickets)

| Criterion | Threshold |
|---|---|
| conviction_score | > 67 |
| predicted_return | > 0 (long-only) |
| backtest_pass_count | ≥ 2 of 4 strategies |
| conformal interval width | < W_max (90th percentile of calibration widths) |

### Decision 11: LSTM Architecture

```python
Bi-LSTM(input_size=31, hidden_size=128, num_layers=3, bidirectional=True)
→ MultiheadAttention(embed_dim=256, num_heads=8)
→ Linear(256,64) → ReLU → Dropout(0.3) → Linear(64,4)
# NO Sigmoid. Output: unbounded ℝ⁴
```

### Decision 12: Training Hyperparameters

| Param | Value |
|---|---|
| Optimizer | AdamW(lr=1e-3, weight_decay=1e-4) |
| LR scheduler | ReduceLROnPlateau(mode='min', patience=5, factor=0.5) |
| Early stopping | 10 consecutive epochs, no val-loss improvement |
| Max epochs | 100 |
| Batch size | 256 (LSTM); pytorch-forecasting chooses for TFT |

---

## 3. Twelve Spec Deviations

These are documented departures from the source PDF, all explicitly approved during brainstorming:

| # | Spec Says | We're Doing | Reason |
|---|---|---|---|
| 1 | LSTM Sigmoid() + BCELoss | Linear() + HuberLoss | BCE expects {0,1}; continuous regression needs Huber |
| 2 | TFT Sigmoid on outputs | Full quantile distributions (q10, q50, q90) | Sigmoid on ~0.02 return ≈ 0.505, contributes nothing |
| 3 | 60/40 LSTM/TFT blend | Uncertainty-aware weighting [0.40, 0.80] | Static weights ignore model's own uncertainty signal |
| 4 | IsotonicRegression calibrator | Locally-weighted split conformal | Isotonic calibrates binary probabilities; doesn't apply to regression |
| 5 | 80/20 train/val split | 70/15/15 train/calibration/validation | Conformal needs distinct calibration set |
| 6 | Filter: P(move) > 0.67 | conviction_score > 67 + backtest + conformal width | P(move) doesn't exist in regression framework |
| 7 | Conviction score undefined | clip(y_pred/sigma * 25 + 50, 0, 100) | Must derive from continuous regression outputs |
| 8 | 4 isotonic models stored | 4 conformal quantiles + 1 residual predictor MLP | Consequence of deviation #4 |
| 9 | LSTM input_size=31 strictly | Same — ticker-agnostic global model (no ticker embedding) | Ticker-aware behavior delegated to TFT |
| 10 | Polygon + Alpha Vantage in failover | yfinance + Alpaca + Stooq (all free) | User scoping; interfaces preserved for later |
| 11 | Backtest: Sharpe > 1.5 only | Sharpe > 1.5 AND total_trades >= 10 AND max_drawdown > -0.40 | Avoid spurious tiny-N passes and exclude blow-ups |
| 12 | Rule 1 says no "alterations" | Deviation #1 is an explicit, documented, approved change | Rule 1 forbids silent alterations; this one is explicit |

---

## 4. Backend Tech Stack & Conventions

### Core Stack

| Layer | Technology | Version |
|---|---|---|
| Runtime | Python | 3.11+ |
| Framework | FastAPI | 0.115.x |
| ORM | SQLAlchemy 2.0 async | 2.0.x |
| DB Driver | asyncpg | 0.30.x |
| Database | PostgreSQL 16 + TimescaleDB | 2.16.x |
| Migrations | Alembic | 1.13.x |
| Package mgmt | uv | latest |
| ML Framework | PyTorch | 2.2.x |
| Training | pytorch-lightning | 2.1.x+ |
| TFT | pytorch-forecasting | 1.0.x+ |
| Indicators | TA-Lib (primary), pandas-ta (fallback) | 0.4.28+ / 0.3.14+ |
| Backtesting | vectorbt | 0.25.x |
| Statistics | scipy | 1.11.x+ |
| Retry | tenacity | 8.2.x+ |
| Logging | loguru | 0.7.x+ |
| Auth | python-jose[cryptography] + argon2-cffi | latest |
| Rate limiting | slowapi | latest |
| CLI | typer | 0.12.x+ |
| Orchestration | Prefect 3 | 3.x |
| Testing | pytest + pytest-asyncio + testcontainers | latest |
| Lint/Format | ruff | latest |

### Feature Layout Convention

Every feature directory follows this structure:
```
features/<name>/
├── models.py          # SQLAlchemy models
├── schemas.py         # Pydantic v2 schemas
├── repository.py      # Data access layer (no raw SQL above this)
├── service.py         # Business logic
├── dependencies.py    # FastAPI dependencies (if needed)
├── router.py          # Router assembly
├── endpoints/         # Individual endpoint handlers
│   ├── list.py
│   ├── detail.py
│   ├── create.py
│   └── ...
├── tests/             # Feature-local tests
│   ├── test_<feature>_service.py
│   └── test_<feature>_endpoints.py
└── features.md        # Feature documentation
```

Sub-features nest the same pattern (e.g., `ml_models/lstm/`, `ml_models/tft/`, `ml_models/ensemble/`, `ml_models/conformal/`).

### Pydantic v2 Patterns

```python
from pydantic import BaseModel, ConfigDict

class UniverseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # NOT orm_mode = True
    id: UUID
    name: str
    display_name: str
    ticker_count: int
```

### Alembic Conventions

- Migrations live in `backend/alembic/`
- `env.py` imports ALL feature models for autogen detection
- Uses **sync engine** (convert async URL to `postgresql+psycopg://...` in env.py)
- First migration: `CREATE EXTENSION IF NOT EXISTS timescaledb;`
- Hypertable calls (`create_hypertable()`) are **hand-added** to migrations — autogen doesn't detect them
- Statement timeout on app connections: 30s

### Error Envelope

All API errors use this structure:
```json
{
  "error_code": "MACHINE_READABLE_CODE",
  "message": "Human-friendly message",
  "details": { "field": "value" },
  "request_id": "req_abc..."
}
```

Codes: `UNIVERSE_NOT_FOUND`, `TICKER_NOT_FOUND`, `INSUFFICIENT_DATA`, `MODEL_NOT_TRAINED`, `BACKTEST_FAILED`, `CONFORMAL_NOT_FIT`, etc.

---

## 5. Data Sources & Failover

### OHLCV Failover Chain

| Priority | Source | Library | Rate Limits |
|---|---|---|---|
| Primary | Yahoo Finance | `yfinance>=0.2.50` | ~2000/hr/IP, unofficial |
| Secondary | Alpaca Market Data | `alpaca-py>=0.30` | Free with paper account |
| Last resort | Stooq | `httpx` (CSV download) | None formally |

### Macro Data

| FRED Series ID | Column Name | Description |
|---|---|---|
| DFF | fed_funds_rate | Federal Funds Effective Rate |
| CPIAUCSL | cpi | Consumer Price Index |
| UNRATE | unemployment | Unemployment Rate |
| GDP | gdp | Gross Domestic Product |
| T10Y2Y | yield_spread_10y_2y | 10Y minus 2Y Treasury Yield |
| VIXCLS | vix | CBOE Volatility Index |
| BAMLH0A0HYM2 | high_yield_spread | High-Yield Master II OAS |

### Retry Configuration

```python
@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3))
```

Per-ticker isolation: if AAPL fails 3 times, MSFT still proceeds. Failed tickers logged in `IngestRun.failed_tickers`.

### Data Cleaning Rules (Non-Negotiable)

- **Timezone stripping**: `df.index = df.index.tz_localize(None)` on every OHLCV frame. TimescaleDB merges break if tz-aware and tz-naive mix.
- **NaN policy**: Raw OHLCV — no NaNs. Macro — forward-fill. Leading NaNs → drop rows.
- **Schema enforcement**: Assert dtypes (float64 for prices, int64 for volume). Mismatches log + coerce.

---

## 6. Data Model Summary

### Tables by Owning Feature

| Table | Feature | Key Notes |
|---|---|---|
| users | auth | Single admin v1; multi-user-ready |
| sessions | auth | Refresh-token-backed |
| universes | universes | Named baskets, system-managed flag |
| tickers | universes | Canonical symbol registry |
| universe_memberships | universes | Time-aware join (added_at, removed_at) |
| ohlcv_bars | data_ingestion | TimescaleDB hypertable on bar_date |
| macro_observations | data_ingestion | TimescaleDB hypertable on observed_date |
| ingest_runs | data_ingestion | Audit + alerting |
| feature_matrix | feature_engineering | TimescaleDB hypertable, 31 cols + 4 targets |
| normalization_stats | feature_engineering | Rolling Z-score parameters |
| training_runs | ml_models | Per-universe, per-week typically |
| model_artifacts | ml_models | 5 active per universe |
| inference_runs | ml_models | Daily |
| predictions | ml_models | Per (ticker, universe, inference_date) |
| backtest_runs | backtesting | Per-universe, weekly |
| backtest_metrics | backtesting | Per (run, ticker, strategy) |
| filter_runs | conviction_tickets | Per inference |
| conviction_tickets | conviction_tickets | The headline output |
| coverage_metrics | monitoring | Conformal coverage tracking |
| feature_drift_metrics | monitoring | Per-feature KL divergence |
| system_alerts | monitoring | Cross-feature alerting |

### Key Indexes

- `(universe_id, removed_at)` on universe_memberships — "active members" queries
- `(ticker_id)` on universe_memberships — "which universes is this ticker in"
- `(ticker_id, bar_date DESC)` on ohlcv_bars — latest-N queries
- `(series_name, observed_date)` on macro_observations — PK
- `(triggered_at DESC)` on ingest_runs — "latest runs"
- `(universe_id, started_at DESC)` on training_runs
- `(universe_id, model_role) WHERE is_active = true` on model_artifacts — partial unique
- `(universe_id, inference_date DESC)` on predictions
- `(ticker_id, inference_date DESC)` on predictions
- `(universe_id, status, conviction_score DESC)` on conviction_tickets — inbox queries
- `(resolution_date, status)` on conviction_tickets — outcome-resolution sweep

---

## 7. Feature-by-Feature Implementation Notes

### Feature 1: Auth & User Accounts

- Single hardcoded admin user, created via `scripts/seed_admin.py`
- JWT access tokens (HS256, 24h) + Postgres-backed hashed refresh tokens (30d sliding)
- Refresh tokens in `sessions` table (boilerplate's session store repurposed)
- `argon2-cffi` for password hashing
- `slowapi` rate limiting: 10/min per IP on login
- Manual password reset: `scripts/reset_password.py` (typer CLI)
- Frontend: JWT in Zustand memory slice; refresh in `HttpOnly Secure SameSite=Strict` cookie
- Endpoints: POST /login, POST /logout, POST /refresh, POST /change-password, GET /sessions, POST /logout-everywhere, GET /me

### Feature 2: Universe Management

- Universe = named, versioned basket of tickers
- Time-aware membership: `added_at` + `removed_at NULL` = active. Removal preserves history.
- Point-in-time snapshots: `?at=<date>` returns members where `added_at <= date AND (removed_at IS NULL OR removed_at > date)`
- Lazy ticker sync: tickers enter registry only when referenced by a universe add (validated against Alpaca)
- `ConstituentSource` Protocol: swappable adapter per index (Wikipedia for S&P 500, iShares CSVs for Russells)
- 3 system-managed universes: S&P 500, Russell 1000, Russell 2000
- Bulk add + CSV import + per-ticker remove
- System-managed universes cannot be deleted or renamed by users

### Feature 3: Data Ingestion (Block A1)

- Failover chain: yfinance (primary) → Alpaca (secondary) → Stooq (last resort)
- `DataFetcher` ABC in `features/data_ingestion/shared/fetcher_base.py`
- FRED macro: 7 series, forward-filled to trading calendar
- Cold-start backfill: 2 years daily OHLCV, 50 tickers/batch
- Daily incremental: after market close, new day's bar
- Gap fill: daily flow detects missing dates, targeted refetch
- Trigger modes: cold_start, daily_scheduled, on_demand, gap_fill
- Output: OHLCVBar + MacroObservation rows + IngestRun audit row

### Feature 4: Feature Engineering (Blocks A2 + A3)

- 31-dimensional contract locked in `feature_schema.py`
- Sub-components: EquityFeatureEngineer, MacroMerger, TargetGenerator, FeatureScaler, TimeSeriesDataset
- Vectorized only — no for loops over rows. TA-Lib primary, pandas-ta fallback.
- Burn-in period: ~200 rows dropped per ticker after calculations
- Lookahead-bias protections: trailing-window only, targets isolated from features, per-ticker scaling
- Rolling 252-day Z-score normalization (never on targets)
- Targets: continuous percentage returns for T+1, T+5, T+10, T+15
- Tensor shape: X=[batch, 252, 31], y=[batch, 4]
- Feature matrix materialized in TimescaleDB (not computed on-the-fly)

### Feature 5: ML Models (Blocks A4 + A5 + A6)

- 1 LSTM per universe (Bi-LSTM 3×128 + 8-head attention + linear head)
- 4 TFTs per universe (one per horizon, QuantileLoss, ticker as static covariate)
- Ensemble: RegimeBlender (uncertainty-aware) + ConformalCalibrator (locally-weighted split conformal)
- Walk-forward 3-way split: 70% train, 15% calibration, 15% validation
- Training: AdamW, ReduceLROnPlateau, early stopping after 10 epochs, max 100
- Conformal: custom NumPy impl (~120 lines), residual predictor MLP, 90% target coverage
- Conviction score: clip(y_pred/sigma * 25 + 50, 0, 100) where sigma = (q90-q10)/2.563
- Model artifact storage: local FS at `~/.mbi/artifacts/` for v1, MinIO-ready swap point
- Active artifact: only one per (universe, model_role). Old artifacts kept for 6 months.

### Feature 6: Backtesting (Block A7)

- 4 strategies: MeanReversion, MomentumCross, VolatilityBreakout, StatArb
- Each inherits from `BaseStrategy` ABC with `generate_signals(df)` → (entries, exits)
- `vectorbt.Portfolio.from_signals()` for execution
- 6 metrics: sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor, total_trades
- Filter pass criteria: sharpe > 1.5 AND total_trades >= 10 AND max_drawdown > -0.40
- Ticker is filter-eligible if it passes ≥ 2 of 4 strategies
- 5-year rolling window default

### Feature 7: Conviction Tickets (Block A8 + Scoring)

- Filter gate: conviction_score > 67 AND predicted_return > 0 AND backtest_passes >= 2 AND conformal_width < W_max
- Up to 4 tickets per ticker (one per horizon)
- Lifecycle: TRADABLE → EXPIRED/REVIEWED → ACTIONED → RESOLVED
- Daily Prefect flow resolves tickets whose horizon ended
- CSV export capped at 10K rows
- Inbox sorted by conviction desc, filterable by universe/horizon/score/backtest/conformal-width

### Feature 8: Monitoring & Model Health

- 7 tracked signals: conformal coverage, train/val loss, conviction-vs-outcome correlation, backtest pass-rate drift, pipeline run success rate, data freshness, feature drift (KL divergence)
- Per-universe model card: last training run, active artifacts, validation metrics, coverage history
- Coverage alert: sustained drop below 80% → critical alert
- Conviction-outcome correlation: Spearman > 0.2 sustained
- Data freshness: alert if > 36 hours since last successful ingest
- Alert routing: loguru + system_alerts table (Slack/email deferred)

### Feature 9: Orchestration (Prefect Flows)

- 7 flows on cron schedules:
  1. `daily_data_refresh` — weekdays 4:20pm ET
  2. `daily_inference` — weekdays 5:30pm ET
  3. `weekly_retrain` — Sundays 6am ET
  4. `weekly_backtest` — Sundays 4am ET
  5. `conformal_coverage_check` — daily 11pm ET
  6. `outcome_resolution` — weekdays 5:00pm ET
  7. `artifact_retention` — weekly Sundays 11pm ET
- Each flow is a thin Prefect layer calling feature services. No business logic in flows.
- Per-task retry: 3 attempts, exponential backoff
- On-failure hook: writes `system_alerts` row
- New artifacts only become `is_active=true` after entire pipeline succeeds

---

## 8. Compatibility Notes (from tech-stack-analysis §5)

Agents MUST be aware of these real friction points:

1. **SQLAlchemy 2.0 async + Alembic**: Alembic doesn't run async migrations natively. Use sync engine in `env.py`, async at runtime.
2. **TimescaleDB + Alembic autogen**: Autogenerate doesn't detect hypertables. Hand-add `create_hypertable()` calls after autogen.
3. **PyTorch + Apple Silicon (MPS)**: MPS works for LSTM but TFT may have rough edges. Document CPU fallback.
4. **yfinance reliability**: Unofficial, breaks for days. Mitigations: tenacity retries, Alpaca+Stooq fallback, `IngestRun.status='partial'`.
5. **Prefect 3 + FastAPI in same Postgres**: Use separate schemas (`prefect` vs `public`). Otherwise migrations fight.
6. **vectorbt + Python version**: Best on Python 3.10–3.11. Pin to 3.11.
7. **pytorch-forecasting + pytorch-lightning**: Tight version coupling. Pin together.
8. **TanStack Query + tab visibility**: TQ pauses polling when tab hidden. Set `refetchIntervalInBackground: true` for training pages.
9. **Pydantic v2 + SQLAlchemy 2.0**: Use `ConfigDict(from_attributes=True)`. NOT `orm_mode = True`.
10. **TimescaleDB hypertable + ON CONFLICT**: Hypertables fully support upserts. Use for incremental ingests.
11. **Loguru + uvicorn logging**: Intercept uvicorn's logger and route through loguru in `core/observability/logging.py`.
12. **Postgres NUMERIC precision**: `NUMERIC(18,8)` for prices/percentages. Don't accidentally cast to float — loses precision.
13. **Statement timeout**: Set `statement_timeout = '30s'` on application connections. Long queries go in Prefect tasks.
14. **Memory for full-universe training**: ~2 GB RAM for feature tensors. Manageable on 8–24 GB VRAM GPUs.
15. **MPS + pytorch_forecasting TFT**: Falls back to CPU. CUDA strongly preferred.

---

## 9. Development Stages Reference

| Stage | Scope | Tasks | Status |
|---|---|---|---|
| S0 | Foundations (walking skeleton) | 9 tasks, 41 sub-tasks | Ready for execution |
| S1 | Auth & Universes (full build) | 8 tasks, 34 sub-tasks | Ready for execution |
| S2 | Data Ingestion (Block A1) | Forthcoming | — |
| S3 | Feature Engineering (Blocks A2+A3) | Forthcoming | — |
| S4 | ML Models (Blocks A4+A5+A6) | Forthcoming | — |
| S5 | Backtesting + Conviction Tickets (Blocks A7+A8) | Forthcoming | — |
| S6 | Monitoring + Orchestration | Forthcoming | — |

---

## 10. Testing Conventions

- **TDD mandatory**: Write tests FIRST. RED → GREEN → REFACTOR.
- **Per-test-database isolation**: testcontainers with `timescale/timescaledb-ha:pg16-latest` image. Each test session gets its own container, migrated to head.
- **Backend**: pytest + pytest-asyncio
- **Feature-local tests**: `features/<name>/tests/test_<feature>_{service,endpoints}.py`
- **Integration tests**: `backend/tests/integration/`
- **E2E**: Playwright in `e2e/` — critical path only
- **Mock external APIs**: Alpaca, yfinance, FRED — all mocked in CI. No live network calls.
- **Test isolation**: Function-scoped transaction rollback within session-scoped testcontainer DB.

---

## 11. Security Conventions

- No secrets in logs (passwords, JWTs, API keys — NEVER logged)
- JWT stored in memory only (Zustand auth slice), not localStorage
- Refresh token in `HttpOnly Secure SameSite=Strict` cookie
- `argon2-cffi` for password hashing (NOT bcrypt)
- Rate limiting: `slowapi` per-IP on login (10/min)
- CORS: explicit frontend origin (NO wildcard)
- `cryptography.Fernet` for encrypting secrets at rest (Alpaca API keys, etc.)
- Manual password reset only (no email infra v1) — `scripts/reset_password.py`
