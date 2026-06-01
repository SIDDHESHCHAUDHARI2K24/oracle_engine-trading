# Tech Stack Analysis — MBI Labs Oracle Engine, Pipeline A

> **Scope**: Project-wide stack validation for Pipeline A v1. Referenced by every stage's `development-plan-S{N}.md`.
> **Status**: Final — all stack decisions locked during brainstorming.
> **Companion document**: `mbi-pipeline-a-v1-design.md` (the full design spec).

This document validates that the locked tech stack supports the v1 feature set, identifies real gaps that need resolution before or during implementation, records assumptions made, and flags compatibility/integration concerns.

---

## 1. Stack Components

| Technology | Role | Version target |
|---|---|---|
| **Python** | Backend runtime. Async-heavy via asyncio. | 3.11+ |
| **FastAPI** | HTTP framework. Async request handling, automatic OpenAPI, Pydantic-driven validation. | 0.115.x |
| **SQLAlchemy 2.0 (async)** | ORM. `AsyncSession` over `asyncpg`. Models live in each feature's `models.py`; all inherit from a common `Base` in `core/models/base.py`. | 2.0.x |
| **asyncpg** | Native async PostgreSQL driver. Powers SQLAlchemy 2.0 async sessions. | 0.30.x |
| **Alembic** | Schema migrations. Lives at `backend/alembic/`. `env.py` imports models from every feature for autogen. | 1.13.x |
| **PostgreSQL** | Primary data store. Houses everything: users, universes, tickers, OHLCV (via Timescale), feature matrices (via Timescale), training runs, model artifact metadata, conviction tickets, monitoring. | 16.x |
| **TimescaleDB extension** | Hypertable extension for time-series tables (`ohlcv_bars`, `macro_observations`, `feature_matrix`, `predictions`). Continuous aggregates and retention policies available when needed. | 2.16.x |
| **uv** | Python package management. Faster than pip, lockfile reproducibility. One `pyproject.toml` for the `backend` package. | latest stable |
| **PyTorch** | Deep learning framework for LSTM and TFT. | 2.2.x |
| **pytorch-lightning** | Training loop abstraction for TFT (per spec a5.1) and a clean way to manage the LSTM training too. | 2.1.x+ |
| **pytorch-forecasting** | Temporal Fusion Transformer implementation. Block A5's core dependency. | 1.0.x+ |
| **TA-Lib** | C-based technical indicator library. RSI, MACD, Bollinger, ATR, SMA — primary engine for Block A2. | 0.4.28+ |
| **pandas-ta** | Pure-Python fallback if TA-Lib's C build fails in a given environment. | 0.3.14+ |
| **vectorbt** | Vectorized backtesting engine (Block A7). Beats pure-Python iteration by orders of magnitude. | 0.25.x |
| **scipy** | Statistical helpers — primarily `scipy.stats.linregress` for the StatArb strategy's rolling OLS. | 1.11.x+ |
| **scikit-learn** | Only used for `StandardScaler` reference patterns; the actual feature normalization is custom rolling Z-score. `IsotonicRegression` is NOT used (replaced by custom conformal). | 1.4.x+ |
| **NumPy** | Universal. Conformal calibrator implementation, broadcast math in blender. | 1.26.x+ |
| **pandas** | Universal. DataFrame manipulation throughout. | 2.2.x+ |
| **tenacity** | Retry + exponential backoff for data fetchers (per spec a1.3). | 8.2.x+ |
| **loguru** | Structured logging (per spec Rule 2). JSON to stdout. | 0.7.x+ |
| **yfinance** | Primary OHLCV source. Free, unofficial, ~2000/hr/IP. Tolerated for v1. | 0.2.50+ |
| **fredapi** | FRED macro series client. Free, 100/day (we use 7 series). | 0.5.2+ |
| **alpaca-py** | Alpaca Market Data SDK. Secondary OHLCV source + paper-trading account integration future hook. | 0.30.x+ |
| **Prefect** | Workflow orchestration. Self-hosted, sharing the same Postgres. Provides the daily/weekly schedule machinery + visual flow dashboard. | 3.x |
| **Vite + React + TypeScript (strict)** | Frontend bundler + framework + types. Strict mode enforces null-safety. | Vite 5.x, React 18.x, TS 5.5+ |
| **React Router v6** | Frontend routing. | 6.x |
| **TanStack Query v5** | Server-state cache & polling. `refetchInterval` per surface. | 5.x |
| **TanStack Table v8** | Headless table primitives for the conviction-ticket inbox and other long lists. | 8.x |
| **React Hook Form + Zod** | Form state + schema-based validation. | RHF 7.x, Zod 3.x |
| **Tailwind CSS + shadcn/ui** | Styling and component primitives. shadcn copied into our repo (no library lock-in). | TW 3.4+ |
| **TradingView Lightweight Charts** | Financial / candlestick / line charts. MIT, ~45KB. | 4.x |
| **Recharts** | General-purpose charts for non-financial metrics (training loss curves, conformal coverage). | 2.x |
| **Zustand** | Client-side state for non-server concerns (auth slice, UI state). Minimal use. | 4.x |
| **pytest + pytest-asyncio** | Backend testing. Tests live within each feature: `feature/<name>/tests/`, `feature/<name>/<sub>/tests/`, plus service-level `tests/`. | latest |
| **vitest** | Frontend unit & component testing. Co-located with source. | latest |
| **Playwright** | E2E browser tests for critical paths (login, create universe, view inbox, view detail). Lives in top-level `e2e/`. Runs in CI against `docker-compose.test.yml`. | latest |
| **ruff** | Backend linting + formatting (replaces black + isort + flake8 + pylint). | latest |
| **ESLint flat config + Prettier** | Frontend linting/formatting. | ESLint 9.x flat |
| **typer** | CLI framework for `scripts/*.py` (admin commands, cold-start backfill, password reset). | 0.12.x+ |
| **argon2-cffi** | Password hashing for `users.password_hash`. | latest |
| **cryptography (Fernet)** | Encrypts any sensitive secrets at rest (future Alpaca API key, future Slack webhook). | latest |
| **python-jose[cryptography]** | JWT issuance and verification. | latest |
| **slowapi** | Rate limiting (per-IP on login). | latest |
| **pnpm** | Frontend package manager. | latest stable |

---

## 2. Coverage Assessment

For each feature's core capabilities, the stack component(s) that handle it.

### Feature 1 — Auth & User Accounts

| Capability | Covered by |
|---|---|
| User CRUD, password hashing | FastAPI endpoints + SQLAlchemy + argon2-cffi |
| JWT issuance/verification | python-jose[cryptography] |
| Session persistence | Postgres `sessions` table + refresh-token-hashed lookup |
| Auth rate limiting | slowapi (per-IP) |
| Manual password reset | typer CLI script in `backend/scripts/` |

### Feature 2 — Universe Management

| Capability | Covered by |
|---|---|
| Universe CRUD with soft-delete | FastAPI + SQLAlchemy + `deleted_at` pattern |
| Time-aware ticker membership | `universe_memberships.added_at` + `removed_at NULL` + indexed point-in-time queries |
| Bulk ticker import | FastAPI multipart CSV endpoint + pandas read + bulk insert with `ON CONFLICT DO NOTHING` |
| System-managed universe seeding | `backend/scripts/seed_universes.py` + checked-in CSV constituent lists |

### Feature 3 — Data Ingestion (Block A1)

| Capability | Covered by |
|---|---|
| Yahoo Finance OHLCV | `yfinance` |
| FRED macro series | `fredapi` |
| Alpaca Market Data secondary | `alpaca-py` |
| Stooq CSV fallback | direct `httpx.AsyncClient` GET + pandas CSV parse |
| Retry + backoff | `tenacity` (per spec a1.3) |
| Per-ticker isolation | Service-layer try/except around each ticker fetch |
| TimescaleDB-backed storage | PostgreSQL + TimescaleDB extension hypertables |
| Timezone stripping | `df.index = df.index.tz_localize(None)` (per spec a1.3) |
| Forward-fill macro | pandas `df.ffill()` in MacroMerger (Block A2) |
| Alerting on >3 failed tickers | loguru log + `system_alerts` insert |

### Feature 4 — Feature Engineering (Blocks A2 + A3)

| Capability | Covered by |
|---|---|
| 19 technical indicators | TA-Lib primary; pandas-ta fallback |
| Macro merge | pandas `join(how='left')` per spec a2.5 |
| Burn-in period cleanup | pandas `df.dropna()` |
| Infinity sweep | NumPy `np.isinf` replace + dropna |
| Target generation (T+1, T+5, T+10, T+15 continuous returns) | pandas `(close.shift(-N) - close) / close` (per spec a3.2) |
| Rolling 252-day Z-score | pandas rolling window stats |
| PyTorch dataset | `torch.utils.data.Dataset` subclass producing `(X[252,31], y[4])` tensors |

### Feature 5 — ML Models (Blocks A4 + A5 + A6)

| Capability | Covered by |
|---|---|
| LSTM architecture | `torch.nn.LSTM` (bidirectional) + `torch.nn.MultiheadAttention` + custom head |
| LSTM training | PyTorch Lightning Trainer OR a custom training loop; `torch.optim.AdamW`, `torch.optim.lr_scheduler.ReduceLROnPlateau`, `torch.nn.HuberLoss` |
| Walk-forward 3-way split | Custom logic in `ml_models/shared/walk_forward.py` |
| TFT Quad-Array | 4 × `pytorch_forecasting.TemporalFusionTransformer` with `QuantileLoss` |
| TFT training | 4 × `pytorch_lightning.Trainer` |
| Uncertainty-aware ensemble blend | Pure NumPy in `ensemble/blender.py` |
| Locally-weighted split conformal | Custom NumPy in `conformal/calibrator.py` (~120 lines) |
| Residual predictor for local weighting | Small `torch.nn.Sequential` MLP (~3 layers) |
| Conformal coverage tracking | `conformal/coverage_tracker.py` + `coverage_metrics` table |
| Model artifact storage | Local filesystem via `core/services/artifact_store.py` |
| Conviction score derivation | NumPy formula in `conviction_tickets/scoring/risk_adjusted.py` |

### Feature 6 — Backtesting (Block A7)

| Capability | Covered by |
|---|---|
| 4 strategies | Subclasses of `BaseStrategy` ABC in `backtesting/strategies/` |
| Portfolio simulation | `vectorbt.Portfolio.from_signals` |
| 6 metrics extraction | vectorbt's built-in `.sharpe_ratio()`, `.max_drawdown()`, etc. |
| StatArb rolling OLS | `scipy.stats.linregress` on rolling 60-day windows |
| Computed `passed` column | Postgres `GENERATED ALWAYS AS (...) STORED` |

### Feature 7 — Conviction Tickets (Block A8 + Scoring)

| Capability | Covered by |
|---|---|
| Filter gate logic | Pure Python in `conviction_tickets/filter/gate.py` |
| Conviction score | NumPy formula in `conviction_tickets/scoring/risk_adjusted.py` |
| Multi-horizon emission | One ticket per horizon that passes the filter |
| Outcome resolution | Daily Prefect flow that joins `conviction_tickets` to `ohlcv_bars` on `resolution_date` |
| CSV export | FastAPI `StreamingResponse` with chunked CSV writer; cap 10K rows |
| Inbox queries | TanStack Query + indexed Postgres queries (`(universe_id, status, conviction_score DESC)`) |

### Feature 8 — Monitoring & Model Health

| Capability | Covered by |
|---|---|
| Conformal coverage tracking | `conformal/coverage_tracker.py` + `coverage_metrics` table |
| Train/val loss curves | Stored in `training_runs.validation_metrics` JSONB |
| Feature drift (KL divergence) | NumPy + scipy.stats; daily flow writes `feature_drift_metrics` |
| Pipeline run success rate | Query against Prefect's schema + monitoring read-model |
| Data freshness check | `MAX(ingest_runs.completed_at)` per universe |
| Conviction-vs-outcome correlation | `scipy.stats.spearmanr` over resolved tickets in rolling window |

### Feature 9 — Orchestration (Prefect Flows)

| Capability | Covered by |
|---|---|
| Daily after-close inference | Prefect cron schedule (weekdays, 5:30pm ET) |
| Weekly retraining | Prefect cron schedule (Sundays, 6am ET) |
| Task-level retries | Prefect's built-in `@task(retries=3, retry_delay_seconds=60)` |
| Flow dashboard | Prefect UI (linked from frontend `/orchestration`) |
| Run history & audit | Prefect's own schema in shared Postgres |
| On-failure alerts | Prefect on-failure hook → `system_alerts` insert |

---

## 3. Gaps Identified

These are real gaps the locked stack does not natively cover.

### Gap 1 — TA-Lib system dependency

**Gap**: TA-Lib is a C library that requires system-level installation (`brew install ta-lib` on macOS, `apt install libta-lib0-dev` on Debian/Ubuntu) before `pip install TA-Lib` works. Not just a Python dep.

**Why it's needed**: Block A2 — every technical indicator the spec mandates.

**Recommendation**:
- Document the system dependency clearly in `backend/README.md` and `docker-compose.dev.yml` (the dev container's Dockerfile should `apt install` it).
- `pandas-ta` is the **declared fallback** (pure Python). The `EquityFeatureEngineer` should try-import TA-Lib first and warn-with-log if it falls back to `pandas-ta`, since `pandas-ta` is ~20× slower.
- For Google Colab usage, document a one-line install snippet at the top of any training notebook.

### Gap 2 — Conformal Prediction implementation

**Gap**: Locked decision is **locally-weighted split conformal**, which no Python library implements out-of-the-box cleanly for PyTorch models. MAPIE (scikit-learn-contrib) supports it for sklearn estimators only.

**Why it's needed**: Block A6 — the entire calibration layer.

**Recommendation**: **Custom lightweight implementation** in `ml_models/conformal/calibrator.py` (~120 lines of NumPy). The math is genuinely simple:

```python
class ConformalCalibrator:
    def fit(self, X_cal, y_pred_cal, y_true_cal):
        residuals = np.abs(y_true_cal - y_pred_cal)
        # Fit the residual predictor (a tiny MLP) on (X_cal, residuals)
        self.residual_predictor.fit(X_cal, residuals)
        # Compute normalized scores
        r_hat_cal = self.residual_predictor.predict(X_cal)
        scores = residuals / (r_hat_cal + 1e-9)
        # Store the (1-alpha) quantile
        self.q = np.quantile(scores, 1 - self.alpha)

    def predict_interval(self, X_new, y_pred_new):
        r_hat = self.residual_predictor.predict(X_new)
        margin = self.q * r_hat
        return y_pred_new - margin, y_pred_new + margin
```

No external dep. Easy to unit-test. Easy to upgrade to ACI later by adding an `update_quantile()` method.

### Gap 3 — Prefect 3 self-hosting in dev

**Gap**: Prefect 3 self-hosted requires a Prefect server + worker setup. Not a one-liner.

**Why it's needed**: Feature 9 (all flows).

**Recommendation**:
- Add a `prefect-server` service to `docker-compose.dev.yml` (the official `prefecthq/prefect:3-latest` image works).
- Configure Prefect to use the same Postgres as the backend, in a separate `prefect` schema (set `PREFECT_API_DATABASE_CONNECTION_URL`).
- Use Prefect's **`serve`** pattern (deployments served from a long-running worker process). The worker can also live in `docker-compose.dev.yml` as `prefect-worker`.
- `backend/scripts/deploy_prefect_flows.py` registers all flows + schedules on startup.

### Gap 4 — Universe constituent CSVs

**Gap**: We need to seed S&P 500, Russell 1000, Russell 2000 ticker lists for the first cold-start backfill. There's no official free API for these constituent lists.

**Why it's needed**: Feature 2 (Universe seeding).

**Recommendation**: Check in **static CSV files** at `backend/scripts/data/universes/{sp500,russell_1000,russell_2000}.csv`, populated from public sources (Wikipedia for S&P 500, iShares ETF holdings exports for Russell). Document a quarterly refresh process. This is a minor data-staleness tradeoff explicitly accepted in scope — Pipeline A models a rolling 2y of bars, so a small membership drift is tolerable.

### Gap 5 — GPU detection and device routing

**Gap**: User has a local GPU available + optionally Google Colab for heavier training. The code needs to detect GPU vs CPU and route the model + tensors appropriately.

**Why it's needed**: Block A4, A5 training (and inference if running locally on the GPU).

**Recommendation**: A small helper in `core/services/torch_device.py`:

```python
def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():    # Apple Silicon
        return torch.device("mps")
    return torch.device("cpu")
```

Every model `.to(device)` and tensor `.to(device)` call routes through this. Trivial cost.

### Gap 6 — Backend Roblox-style structured logging without structlog

**Gap**: Feenix uses structlog; per the manifesto's Rule 2, MBI uses loguru. The two have very different APIs.

**Why it's needed**: Cross-cutting observability.

**Recommendation**: Use loguru with JSON serialization enabled:

```python
# core/observability/logging.py
from loguru import logger
import sys, json

logger.remove()
logger.add(sys.stdout, format="{message}", serialize=True)
logger.configure(extra={"service": "mbi-backend"})

# Usage:
logger.bind(request_id=req_id, user_id=user_id, universe_id=u_id).info("Inference complete")
```

`loguru.bind()` produces structured JSON with all bound context. Equivalent to structlog's `bind_contextvars` for our needs.

### Gap 7 — TimescaleDB extension installation

**Gap**: TimescaleDB isn't part of vanilla Postgres. The Docker image `timescale/timescaledb:latest-pg16` is required (not `postgres:16`).

**Why it's needed**: Hypertables for `ohlcv_bars`, `macro_observations`, `feature_matrix`, `predictions`.

**Recommendation**:
- Use `timescale/timescaledb-ha:pg16` (HA variant — includes Timescale toolkit) in `docker-compose.dev.yml`.
- First Alembic migration enables the extension: `CREATE EXTENSION IF NOT EXISTS timescaledb;`
- Subsequent migrations create hypertables via `SELECT create_hypertable('ohlcv_bars', 'bar_date', if_not_exists => TRUE);`

### Gap 8 — Frontend OpenAPI type generation

**Gap**: We want TypeScript types on the frontend that match the FastAPI backend's Pydantic schemas. Drift = bugs.

**Why it's needed**: Every frontend feature.

**Recommendation**: `openapi-typescript` (the popular generator). Add a `pnpm run gen:api` script that:
1. Fetches `http://localhost:8000/openapi.json` from the running backend
2. Generates `frontend/src/core/types/api.ts`
3. Run on backend changes (manual for v1; CI gate later)

### Gap 9 — Backend testing fixtures for TimescaleDB

**Gap**: Postgres rollback patterns (transactional fixtures) work fine, but TimescaleDB partition creation can complicate test isolation.

**Why it's needed**: Pretty much every backend test.

**Recommendation**: Use a **per-test-database** pattern (each test gets its own Postgres database via testcontainers). Higher setup cost (a few seconds) but bulletproof isolation. Alternative: transactional rollback fixtures with a careful list of "what NOT to create per-test." We pick per-test-database for v1; it's simpler to reason about.

### Gap 10 — `loc_xxx` / `ct_xxx` short-ID generation pattern

**Gap**: We want short, human-readable IDs for conviction tickets (`ct_<base32>`) and possibly universes (`uni_<base32>`), in addition to UUIDs internally.

**Why it's needed**: Feature 7 (conviction tickets), Feature 2 (universes).

**Recommendation**: stdlib `secrets.token_hex(6)` + base32 encode → ~12 chars. Stored alongside the UUID primary key. Same pattern Feenix uses for `loc_xxx`.

---

## 4. Assumptions

Decisions made to fill minor gaps without blocking. The user can override any of these during stage reviews.

1. **Backend formatter/linter is `ruff`** (Gap-adjacent). Configuration in `backend/pyproject.toml`.
2. **Frontend formatter is Prettier**, linter is ESLint flat config.
3. **TA-Lib is the primary technical-indicator library**, with `pandas-ta` as the documented Python-only fallback. Install instructions live in `backend/README.md`.
4. **GPU device routing is centralized** in `core/services/torch_device.py` (Gap 5).
5. **Universe constituent CSVs are checked in** under `backend/scripts/data/universes/` and refreshed quarterly via a documented runbook.
6. **OpenAPI client generation is `openapi-typescript`** (Gap 8). Manual `pnpm run gen:api` for v1; CI gate later.
7. **Backend test isolation is per-test-database via testcontainers** (Gap 9). Slower than transactional rollback but bulletproof.
8. **Pydantic v2** throughout. Schemas live in each feature's `schemas.py`.
9. **API versioning prefix is `/api/v1`** for all dashboard endpoints. Major-version bumps via parallel routers.
10. **CORS configuration**: explicitly allow the frontend's origin (per-environment via env var). No wildcard.
11. **JWT TTL**: 24 hours for access tokens, 30 days for refresh tokens (sliding).
12. **Cookies**: refresh-token cookie is `HttpOnly Secure SameSite=Strict` (locked down by default).
13. **Connection pool**: backend uses 10 base + 10 overflow.
14. **TimescaleDB Docker image**: `timescale/timescaledb-ha:pg16-latest` in dev. Single Postgres for both application data and Prefect.
15. **Prefect Postgres schema**: `prefect` (Prefect's tables) + `public` (application tables) within the same database.
16. **Cold-start backfill is documented as a manual one-time step** via `backend/scripts/initial_backfill.py`. Subsequent ingests are daily incremental via Prefect.
17. **CI is GitHub Actions**. Workflows: `test-backend.yml`, `test-frontend.yml`, `lint.yml`, `e2e.yml`.
18. **The "system admin" user is created at first boot** via `backend/scripts/seed_admin.py`. Credentials live in `.env` (admin email + admin password). Never checked in.
19. **Model artifact files** named `{universe_slug}_{model_role}_{training_run_id}.pt` on disk; the full path is stored in `model_artifacts.artifact_path`.
20. **Conformal alpha defaults to 0.10** (90% target coverage). Configurable per-universe via `universes.metadata->>'conformal_alpha'`.

---

## 5. Compatibility Notes

Real friction points between locked technologies.

1. **SQLAlchemy 2.0 async + Alembic migrations**: Alembic doesn't run async migrations natively. Standard pattern: write migrations using a sync engine (Alembic's default), apply them via `alembic upgrade head`. Models are async at runtime; migration *operations* are sync. Well-documented; flag so no one over-engineers.

2. **TimescaleDB + Alembic autogen**: Alembic's autogenerate doesn't know about Timescale-specific objects (hypertables, continuous aggregates). After autogen, manually add the `create_hypertable()` calls to each migration. The first migration MUST include `CREATE EXTENSION IF NOT EXISTS timescaledb;` before any hypertable conversion.

3. **PyTorch + Apple Silicon (MPS)**: For developers on M-series Macs, MPS works for LSTM but pytorch-forecasting + TFT may have rough edges on MPS (some ops fall back to CPU). Document: "If you're on Apple Silicon and training takes longer than expected, fall back to `CUDA_VISIBLE_DEVICES=''` + CPU, or train on Colab."

4. **yfinance reliability**: yfinance is unofficial and breaks for days at a time historically. Three mitigations in place: (a) `tenacity` retries, (b) Alpaca + Stooq fallback chain, (c) `IngestRun.status='partial'` lets the rest of the pipeline continue with stale data while alerting.

5. **Prefect 3 + FastAPI in the same Postgres**: Both can share the database but should use **separate schemas** (`prefect` vs `public`). Otherwise Alembic and Prefect's own migrations will fight over the `alembic_version` table or its equivalent.

6. **vectorbt + Python version**: vectorbt currently has best compatibility with Python 3.10–3.11. Python 3.12 has known issues with some numba-jitted code. Pin to 3.11.

7. **pytorch-forecasting + PyTorch Lightning version drift**: These two libraries have a tight version coupling. Pin them together (`pytorch-forecasting==1.0.x` + `pytorch-lightning==2.1.x`). Bumping one without the other risks subtle bugs.

8. **TanStack Query + tab visibility**: TQ pauses polling when tab is hidden by default. For the conviction-ticket inbox, that's fine. For an active training run page, we set `refetchIntervalInBackground: true`.

9. **Pydantic v2 + SQLAlchemy 2.0**: Use `model_config = ConfigDict(from_attributes=True)`. The old `orm_mode = True` pattern doesn't apply.

10. **TimescaleDB hypertable + ON CONFLICT**: Hypertables fully support upserts via `INSERT ... ON CONFLICT (ticker_id, bar_date) DO UPDATE`. Use this for incremental ingests where occasionally a back-fill overlaps a previous fetch.

11. **Loguru + uvicorn logging**: uvicorn's default logging is `logging`, not loguru. We intercept uvicorn's logger and route through loguru in `core/observability/logging.py`. Standard pattern; easy to get wrong.

12. **Postgres NUMERIC precision**: We use `NUMERIC(18,8)` for prices and percentages. Confirm asyncpg's deserialization round-trips correctly (it does — `Decimal` objects in Python). Don't accidentally cast to `float` in the service layer; that loses precision.

13. **Statement timeout**: Set `statement_timeout = '30s'` on the application-level connection. Long-running queries (a full backtest, an inference batch) live in Prefect tasks with their own timeout management; the application connection isn't where they should run.

14. **Memory for full-universe training**: For Russell 3000 × 252-day windows × 31 features × 4 horizons targets in float32 → roughly **2 GB** of feature tensor RAM. Manageable on most modern GPUs (8–24 GB VRAM). Document this in the cold-start training runbook.

15. **MPS support for `pytorch_forecasting.TemporalFusionTransformer`**: Falls back to CPU for some ops. CUDA strongly preferred for TFT training.

---

## 6. Decisions That Are NOT Gaps

Worth recording so we don't relitigate during stage reviews:

- **No caching layer in v1** (Valkey deferred). Repository abstraction is cache-friendly so adding later is one place.
- **No `shared/` package**. Pipeline A v1 is a single deployable backend. When Pipeline B comes online as a separate service, we'll extract a `shared/` package.
- **No multi-user auth in v1**. Single hardcoded admin. Schema reserves multi-user from day one.
- **No email infrastructure**. No automated password reset. Manual CLI runbook only.
- **No Polygon / Alpha Vantage** for v1 data sources. Interface preserved for swap when paid sources are justified.
- **No per-feature thresholds for the impression algorithm** — wait, this is Feenix language. For MBI: **no per-universe conformal-alpha configurability beyond a single column**. One alpha per universe in v1.
- **No Prometheus / OpenTelemetry**. loguru JSON to stdout + Prefect dashboard cover observability for v1.
- **No SSE / WebSockets / real-time pushes**. Polling everywhere.
- **No paper-trading sandbox or execution layer**. Conviction tickets are read-only outputs. The user takes manual action on them outside the system.
- **No short positions**. Long-only filter in v1. Schema reserves the `SHORT` direction enum value.
- **No A/B model testing**. Single active artifact per `(universe, role)`. Schema supports champion/challenger via a future enum bump.
- **No automatic intraday inference**. Daily-after-close only.
- **No RL / continuous-learning weight updates**. Static weekly retrain. Schema captures outcomes so an RL reward signal can be added later as Block A9.

---

## 7. Cross-references

- Full design spec: `mbi-pipeline-a-v1-design.md`
- Per-stage development plans: `development-plan-S0.md` through `development-plan-S6.md` (forthcoming).
- Each stage plan will begin with a "Stage Dependency Map" section.
