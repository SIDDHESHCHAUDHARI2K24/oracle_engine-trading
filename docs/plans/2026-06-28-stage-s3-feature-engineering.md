# Stage S3 — Feature Engineering (Blocks A2 + A3) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform raw OHLCV + macro from S2 into the 31-dimensional feature tensor consumed by ML models — implementing the locked feature schema, TA-Lib technical engine, macro left-join aligner, continuous-return target generation, lookahead-safe rolling 252-day Z-score normalization, and PyTorch `TimeSeriesDataset` producing `[252, 31]` / `[4]` tensors.

**Architecture:** Strictly per-ticker pipeline (preserving isolation and lookahead protection), parallelized across CPU cores via joblib, with hybrid increment strategy (full recompute on backfill/schema-change, trailing-window-seeded incremental on daily). Normalized features land in `feature_matrix` hypertable; rolling mean/std snapshots in `normalization_stats` for reproducibility.

**Tech Stack:** Python 3.12+, TA-Lib 0.6.8+ (primary), pure-pandas fallback, torch 2.12+, joblib 1.5+, SQLAlchemy 2.0 async + asyncpg, TimescaleDB hypertables, Prefect 3, pytest + testcontainers.

---

## Prerequisites (completed)

- S2 complete: `ohlcv_bars` + `macro_observations` populated; trading calendar available; Prefect daily flow running.
- Dependencies added: TA-Lib, torch, joblib.
- **pandas-ta removed** — incompatible with pandas>=3.0.3 (numba conflict). Pure-pandas fallback implemented instead.

## Dependency Map

```
P3.T0 ───────────────────── (prerequisite — deps + graphify)
  │
P3.T1 ───┬── P3.T2 ────┐   ← T2 + T3 parallel after T1
         └── P3.T3 ────┤
                       │
          P3.T4 ◄──────┘
                       │
          P3.T5 ◄──────┘
                       │
          P3.T6 ◄──────┘
               │
       ┌───────┴───────┐   ← T7 + T8 parallel after T6
       ▼               ▼
    P3.T7          P3.T8
       │               │
       └───────┬───────┘
               ▼
          P3.T9 ◄──────┘  ← verification capstone
```

**Critical path:** T0 → T1 → T2 → T4 → T5 → T6 → T7 → T9
**Parallelizable:** T2+T3 (after T1), T7+T8 (after T6)

---

## Task P3.T0: Prerequisites — Dependencies + Graphify

**Goal:** Add missing dependencies (TA-Lib, torch, joblib) and update knowledge graph.

**Files:**
- Modify: `backend/pyproject.toml`
- Run: `graphify update .`

**ACs:** uv sync succeeds, TA-Lib importable, graphify populated with code nodes.

**Status:** COMPLETE — TA-Lib 0.6.8, torch 2.12.1, joblib 1.5.3 installed.

---

## Task P3.T1: Feature Schema Contract + Migration

**Goal:** Define the locked 31-column contract as the single source of truth + create DB tables.

**Files to create:**
- `backend/app/features/feature_engineering/__init__.py`
- `backend/app/features/feature_engineering/shared/__init__.py`
- `backend/app/features/feature_engineering/shared/feature_schema.py`
- `backend/app/features/feature_engineering/shared/tests/__init__.py`
- `backend/app/features/feature_engineering/shared/tests/test_feature_schema.py`
- `backend/app/features/feature_engineering/models.py`
- `backend/app/features/feature_engineering/__init__.py`
- Alembic migration: `backend/alembic/versions/<rev>_add_feature_matrix.py`

**Sub-task P3.T1.S1: Define feature_schema contract**
- Create `FeatureSpec` dataclass with fields: `name`, `category` (RAW/TECHNICAL/MACRO), `dtype`, `source_lib`, `window`
- Define all 31 features + 4 targets in order, matching design §5 exactly
- `FEATURE_SCHEMA_VERSION = "v1.0"` constant
- Helper accessors: `input_feature_names()`, `target_names()`, `raw_names()`, `technical_names()`, `macro_names()`
- Test: assert `len(input_feature_names()) == 31`, assert tagret count == 4, verify order

**Sub-task P3.T1.S2: Database migration**
- Create `feature_matrix` table: PK `(ticker_id, bar_date, feature_schema_version)`, 31 feature columns + 4 target columns, computed_at, hypertable on bar_date
- Create `normalization_stats` table: PK `(ticker_id, bar_date, feature_name)`, hypertable on bar_date
- Index: `(ticker_id, bar_date DESC)` on feature_matrix
- Upgrade/downgrade round-trip

**Dependencies:** S2 (tickers, ohlcv_bars exist)
**Risk:** Medium — schema_version in PK enables clean future migrations

---

## Task P3.T2: Technical Feature Engine (Block A2.1)

**Goal:** Compute all 19 technical features vectorized (TA-Lib primary, pure-pandas fallback).

**Files to create:**
- `backend/app/features/feature_engineering/technical/__init__.py`
- `backend/app/features/feature_engineering/technical/base.py`
- `backend/app/features/feature_engineering/technical/equity_engineer.py`
- `backend/app/features/feature_engineering/technical/tests/__init__.py`
- `backend/app/features/feature_engineering/technical/tests/test_equity_engineer.py`

**Sub-task P3.T2.S1: BaseFeatureEngineer ABC**
- Abstract `generate_features(df: pd.DataFrame) -> pd.DataFrame`
- Window config from feature_schema
- Append-only contract documented

**Sub-task P3.T2.S2: Write tests (TDD — RED first)**
- All 19 features covered with value assertions
- Lookahead check: row at `t` identical when computed on `df[:t]` vs `df[:t+10]`
- TA-Lib/pandas parity check (within tolerance)

**Sub-task P3.T2.S3: Implement EquityFeatureEngineer**
- Try-import TA-Lib first; on ImportError, fall back to pure-pandas implementation with logged warning
- All 19 indicators computed vectorized
- Raw OHLCV columns never overwritten
- Test pass (GREEN)

**Formulas (locked per spec a2.4):**
- `returns_1d/5d/10d/20d` = `close.pct_change(periods=N)`
- `rsi_14` = RSI with 14-period lookback
- `macd/macd_signal/macd_hist` = MACD triple from close
- `bb_upper/middle/lower` = Bollinger Bands from close (20-period, 2 std)
- `bb_width` = `(upper - lower) / middle`
- `atr_14` = ATR with 14-period lookback
- `volatility_20d` = `returns_1d.rolling(20).std() * sqrt(252)`
- `volume_z_score` = `(volume - volume.rolling(20).mean()) / volume.rolling(20).std()`
- `sma_50/200` = 50/200-day SMA
- `price_to_sma50/200` = `close / sma_50` and `close / sma_200`

**Dependencies:** P3.T1.S1 (feature_schema)
**Risk:** Medium — TA-Lib C lib may be unavailable; pure-pandas fallback must produce parity

---

## Task P3.T3: Macro Merger (Block A2.2)

**Goal:** Left-join 7 forward-filled macro series onto each ticker's trading-day index.

**Files to create:**
- `backend/app/features/feature_engineering/alignment/__init__.py`
- `backend/app/features/feature_engineering/alignment/macro_merger.py`
- `backend/app/features/feature_engineering/alignment/tests/__init__.py`
- `backend/app/features/feature_engineering/alignment/tests/test_macro_merger.py`

**Sub-task P3.T3.S1: Implement MacroMerger**
- Left-join macro_df on equity_df's date index
- Assert no macro values on non-trading days
- Post-join macro NaNs only in leading burn-in region

**Sub-task P3.T3.S2: Write tests**
- Equity row count preserved after merge
- All 7 macro columns attached
- Forward-fill propagation across release gaps verified
- Leading-macro-NaN case handled

**Parallel with:** P3.T2
**Dependencies:** P3.T1.S1

---

## Task P3.T4: Target Generator (Block A3.1)

**Goal:** Compute 4 continuous forward returns using exact subtraction formula.

**Files to create:**
- `backend/app/features/feature_engineering/tensor_prep/__init__.py`
- `backend/app/features/feature_engineering/tensor_prep/target_generator.py`
- `backend/app/features/feature_engineering/tensor_prep/tests/__init__.py`
- `backend/app/features/feature_engineering/tensor_prep/tests/test_target_generator.py`

**Sub-task P3.T4.S1: Implement TargetGenerator**
- `target_t{N} = (close.shift(-N) - close) / close` for N ∈ {1, 5, 10, 15}
- Use EXACT subtraction (NOT pct_change — avoids inverse-denominator errors)
- Trailing unresolved rows stored as NULL

**Sub-task P3.T4.S2: Write tests**
- Forward direction checked: `target_t5[t] == (close[t+5] - close[t]) / close[t]`
- Last 15 rows have NULL target_t15
- Targets isolated from feature columns (not touched by scaler)

**Dependencies:** P3.T2 (technical features), P3.T3 (macro merge)
**Risk:** Medium — negative shift sign bug (classic)

---

## Task P3.T5: Feature Scaler (Block A3.2 — Rolling Z-score)

**Goal:** Apply rolling 252-day Z-score per feature per ticker with zero lookahead leakage.

**Files to create:**
- `backend/app/features/feature_engineering/tensor_prep/feature_scaler.py`
- `backend/app/features/feature_engineering/tensor_prep/tests/test_feature_scaler.py`

**Sub-task P3.T5.S1: Write lookahead-safety tests (TDD — RED first)**
- Trailing-window-only: scaled value at `t` identical whether computed on `df[:t+1]` or `df[:t+100]`
- Target isolation: targets pass through unchanged
- Per-ticker isolation: AAPL stats never influence MSFT
- Stats capture: normalization_stats match manual computation
- Zero-std handling: constant feature → output 0, no inf

**Sub-task P3.T5.S2: Implement FeatureScaler**
- `df[feat].rolling(window=252, min_periods=252).mean()` / `.std()`
- Only 31 input features (from schema); targets explicitly excluded
- Zero-std → output 0
- Capture mean/std per (ticker, date, feature) for normalization_stats
- All P3.T5.S1 tests GREEN

**Dependencies:** P3.T4
**Risk:** HIGH — This is the highest-risk correctness surface in S3. Lookahead leakage here makes all downstream metrics deceptive.

---

## Task P3.T6: FeatureOrchestrator + Parallelism

**Goal:** Per-ticker pipeline orchestration with joblib parallelization across CPU cores.

**Files to create:**
- `backend/app/features/feature_engineering/service.py`
- `backend/app/features/feature_engineering/repository.py`
- `backend/app/features/feature_engineering/schemas.py`
- `backend/app/features/feature_engineering/dependencies.py`
- `backend/app/features/feature_engineering/router.py`
- `backend/app/features/feature_engineering/endpoints/__init__.py`

**Sub-task P3.T6.S1: Per-ticker pipeline**
- Pure function: `process_ticker(ticker_id, ohlcv_df, macro_df) -> (feature_df, stats_df)`
- Pipeline: technical engine → macro merge → target generation → scaler → sanitize
- Sanitization order: infinity sweep → dropna (burn-in) → schema assert (31 features + 4 targets)
- Persist via repository (bulk upsert)

**Sub-task P3.T6.S2: Parallelism**
- `joblib.Parallel(n_jobs=-1)(delayed(process_ticker)(t) for t in tickers)`
- Per-worker DB session (never shared)
- Shared macro frame read-only
- `n_jobs` configurable
- Per-ticker try/except isolation

**Dependencies:** P3.T5, P3.T2, P3.T3, P3.T4
**Risk:** Medium — joblib workers must not share DB sessions

---

## Task P3.T7: PyTorch TimeSeriesDataset (Block A3.3)

**Goal:** `TimeSeriesDataset(torch.utils.data.Dataset)` yielding `[252, 31]` / `[4]` float32 tensors.

**Files to create:**
- `backend/app/features/feature_engineering/tensor_prep/dataset.py`
- `backend/app/features/feature_engineering/tensor_prep/tests/test_dataset.py`

**Sub-task P3.T7.S1: Implement TimeSeriesDataset**
- Sliding 252-day lookback window; window at row `t` uses features `[t-251, t]`, targets at `t`
- Per-ticker valid-window index map (no cross-ticker straddle)
- NaN-target windows excluded
- Output dtype: float32

**Sub-task P3.T7.S2: Write tests**
- Single `__getitem__` shape: `X[252, 31]` + `y[4]`
- `DataLoader(batch_size=8)` shapes: `[8, 252, 31]` / `[8, 4]`
- No-straddle test: window at ticker boundary doesn't pull previous ticker's rows
- Unresolved-target exclusion verified
- X carries normalized (not raw) values

**Parallel with:** P3.T8
**Dependencies:** P3.T6

---

## Task P3.T8: Backfill + Prefect Daily Increment

**Goal:** Full-recompute backfill + trailing-window-seeded daily increment wired into Prefect.

**Files to modify:**
- `backend/app/orchestration/flows/daily_data_refresh.py` — add feature compute task after ingestion
- `backend/app/orchestration/tasks/data_tasks.py` — add feature compute task

**Files to create:**
- `backend/scripts/feature_backfill.py`

**Sub-task P3.T8.S1: Full-recompute backfill**
- Script/service calling parallel FeatureOrchestrator over all active tickers
- Idempotent via schema-versioned upsert
- Progress logging, documented runtime

**Sub-task P3.T8.S2: Trailing-window-seeded incremental**
- For each ticker: find latest feature_matrix date, load OHLCV from `(latest - 252 trading days)` using trading calendar (not naive row count)
- Run full per-ticker pipeline on seed+new data
- Upsert ONLY rows after latest existing date

**Sub-task P3.T8.S3: Bit-identical test + Prefect wiring**
- **THE CRITICAL TEST**: incremental output == full recompute for same dates (within float tolerance)
- Extend Prefect `daily_data_refresh` flow: add feature compute task after ingestion
- Flow failure on features doesn't corrupt prior good rows

**Parallel with:** P3.T7
**Dependencies:** P3.T6, S2 (Prefect daily flow)
**Risk:** HIGH — Seed-window wrong → silent indicator corruption. The bit-identical test is THE gate.

---

## Task P3.T9: Inspect API + Lookahead Audit + E2E

**Goal:** API endpoints, lookahead-audit suite (release-blocking), frontend inspect page, docs.

**Files to create:**
- `backend/app/features/feature_engineering/endpoints/trigger.py`
- `backend/app/features/feature_engineering/endpoints/inspect.py`
- `backend/app/features/feature_engineering/features.md`
- `backend/app/features/feature_engineering/tests/`
- `tests/lookahead_audit/` — dedicated audit suite
- `frontend/src/features/feature_engineering/` — inspect page

**Sub-task P3.T9.S1: API endpoints**
- `POST /api/v1/feature_engineering/trigger` — admin-only, full/incremental, universe/ticker scope
- `GET /api/v1/feature_engineering/inspect?ticker=AAPL&date=2026-05-28` — all 31 raw + normalized values + 4 targets + stats for one cell
- Wire into app.py

**Sub-task P3.T9.S2: Lookahead audit suite (release-blocking gate)**
- Compute pipeline on `history[:t]` vs `history[:t+K]`, assert all past features identical
- Covers: technical features, scaled features, dataset windows
- Documented as release-blocking quality gate
- A single failing cell = release blocker

**Sub-task P3.T9.S3: Frontend + integration tests + docs**
- `/features/inspect` page: ticker/date pickers → data-grid table
- Integration test: seed OHLCV+macro fixture → compute → inspect endpoint
- `features.md`: 31-dim contract, lookahead protections, hybrid increment docs

**Dependencies:** P3.T7, P3.T8
**Risk:** Medium

---

## Task Summary

| Task | Effort | Risk | Parallel? | Key Dependency |
|---|---|---|---|---|
| P3.T0 | S (2h) | Low | No | None |
| P3.T1 | M (1d) | Med | No | S2 |
| P3.T2 | L (2d) | Med | With T3 | T1 |
| P3.T3 | M (1d) | Low | With T2 | T1 |
| P3.T4 | M (1d) | Med | No | T2+T3 |
| P3.T5 | L (2d) | **High** | No | T4 |
| P3.T6 | L (2d) | Med | No | T5 |
| P3.T7 | M (1d) | Med | With T8 | T6 |
| P3.T8 | L (2d) | **High** | With T7 | T6 |
| P3.T9 | M (1d) | Med | No | T7+T8 |
| **Total** | **11-15d** | — | — | — |

---

## Top Risks

| ID | Risk | Mitigation | Owner Task |
|---|---|---|---|
| R1 | Lookahead bias leaks into features | Trailing-window-only math; target isolation; dedicated lookahead-audit suite as release gate | P3.T9.S2 |
| R2 | Incremental seed window wrong → silent indicator corruption | Bit-identical incremental-vs-full test; seed window from trading calendar | P3.T8.S3 |
| R3 | TA-Lib unavailable (C lib install friction) | Pure-pandas fallback with logged warning; parity test within tolerance | P3.T2.S3 |
| R4 | Cross-ticker window straddle in dataset | Per-ticker valid-window index; no-straddle test | P3.T7.S1 |
| R5 | Negative-shift target sign bug | Exact subtraction formula per spec; forward-direction test | P3.T4.S1 |
| R6 | joblib workers sharing a DB session | One session per worker process; read-only shared macro frame | P3.T6.S2 |
| R7 | Zero-std feature → inf after Z-score | Explicit zero-std handling → output 0 | P3.T5.S2 |

---

## Assumptions
- Persistence: normalized features in `feature_matrix` + rolling mean/std in `normalization_stats` (locked)
- Feature computation is per-ticker, parallelized across CPU cores via joblib (locked)
- Increment strategy: hybrid — full recompute on backfill/schema change; trailing-window-seeded incremental on daily (locked)
- TA-Lib primary, pure-pandas fallback (pandas-ta dropped due to dependency conflict)
- The 31-dim feature schema is locked in `feature_schema.py`; changes require schema-version bump
- Lookahead-audit suite is a release-blocking quality gate

---

## Cross-references
- Design spec: `mbi-pipeline-a-v1-design.md` (§5 Feature Engineering, §14 deviations)
- Stack validation: `tech-stack-analysis.md` (§3 Gap 1 TA-Lib, §5 compat notes)
- Previous stage: `development-plan-S2.md` (OHLCV + macro + trading calendar this consumes)
- Next stage: S4 — ML Models (Blocks A4 + A5 + A6)

---

**End of Stage S3 Plan**
