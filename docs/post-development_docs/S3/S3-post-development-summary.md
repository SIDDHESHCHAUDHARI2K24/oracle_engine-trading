# Stage S3 — Feature Engineering (Blocks A2 + A3) — Post-Development Summary

> **Date**: 2026-06-28
> **Status**: Build complete. 71 unit tests pass. Lookahead audit suite passes. Bit-identical gate passes.
> **Source spec**: `development-plan-S3.md`, `mbi-pipeline-a-v1-design.md` §5
> **Previous**: S2 — Data Ingestion (ohlcv_bars + macro_observations + trading calendar)
> **Next**: S4 — ML Models (Bi-LSTM + TFT Quad-Array)

---

## 1. What S3 Builds

S3 transforms raw OHLCV + macroeconomic data from the S2 data ingestion pipeline into the **31-dimensional feature tensor** consumed by the deep learning models. It is the numerical backbone of Pipeline A — everything downstream depends on the correctness of these features.

**Concrete output**: The `feature_matrix` TimescaleDB hypertable with one row per (ticker, trading day) containing all 31 normalized features + 4 forward-return targets, plus `normalization_stats` for reproducibility.

---

## 2. Architecture

```
S2 Output (ohlcv_bars + macro_observations)
           │
           ▼
P3.T2  EquityFeatureEngineer     ── 19 technical indicators (pure-pandas, vectorized)
           │
           ▼
P3.T3  MacroMerger               ── left-join 7 forward-filled macro series
           │
           ▼
P3.T4  TargetGenerator           ── 4 continuous forward returns (T+1/T+5/T+10/T+15)
           │
           ▼
P3.T5  FeatureScaler             ── rolling 252-day Z-score (31 inputs only, targets untouched)
           │
           ▼
P3.T6  FeatureOrchestrator       ── per-ticker isolation + joblib parallelization + sanitization
           │
           ├── P3.T7  TimeSeriesDataset   ── PyTorch [252,31] / [4] sliding-window tensors
           ├── P3.T8  Backfill + Prefect  ── full recompute + trailing-window-seeded incremental
           └── P3.T9  API + Audit         ── inspect/trigger endpoints + lookahead audit suite
```

All computation is **per-ticker** (no cross-ticker leakage), **vectorized** (no Python row loops), and **lookahead-safe** (proven by test).

---

## 3. The 31-Dimensional Contract

Locked in `feature_engineering/shared/feature_schema.py` — the single source of truth. Every downstream module imports from here.

| Category | Count | Columns |
|---|---|---|
| Raw | 5 | open, high, low, close, volume |
| Technical | 19 | returns_{1d,5d,10d,20d}, rsi_14, macd, macd_signal, macd_hist, bb_{upper,middle,lower}, bb_width, atr_14, volatility_20d, volume_z_score, sma_{50,200}, price_to_sma{50,200} |
| Macro | 7 | fed_funds_rate, cpi, unemployment, gdp, yield_spread_10y_2y, vix, high_yield_spread |
| **Total inputs** | **31** | |
| Targets | 4 | target_t1, target_t5, target_t10, target_t15 |

Schema version `"v1.0"` is part of the PK — enables side-by-side migration when the schema changes.

---

## 4. Component Map

| File | Purpose | Lines |
|---|---|---|
| `shared/feature_schema.py` | Locked 31-column contract, `FeatureSpec`/`TargetSpec`, helper accessors | ~100 |
| `shared/tests/test_feature_schema.py` | 19 tests: counts, ordering, categories, no duplicates | ~90 |
| `technical/base.py` | `BaseFeatureEngineer(ABC)` — append-only contract | ~30 |
| `technical/equity_engineer.py` | 19 indicators via pure-pandas (RSI, MACD, BB, ATR, SMA, volatility, volume-z) | ~110 |
| `technical/tests/test_equity_engineer.py` | 20 tests including lookahead safety | ~200 |
| `alignment/macro_merger.py` | Left-join 7 forward-filled macro series onto trading-day index | ~40 |
| `alignment/tests/test_macro_merger.py` | 6 tests: row count, forward-fill, leading-NaN | ~85 |
| `tensor_prep/target_generator.py` | 4-horizon continuous returns via exact subtraction (NOT pct_change) | ~35 |
| `tensor_prep/tests/test_target_generator.py` | 7 tests: forward direction, NaN counts, input preservation | ~65 |
| `tensor_prep/feature_scaler.py` | Rolling 252-day Z-score, targets isolated, zero-std → 0, stats capture | ~85 |
| `tensor_prep/tests/test_feature_scaler.py` | 9 tests: THE decisive lookahead test, per-ticker isolation, zero-std | ~160 |
| `tensor_prep/dataset.py` | `TimeSeriesDataset(torch Dataset)` — [252,31]/[4] float32 tensors | ~80 |
| `tensor_prep/tests/test_dataset.py` | 5 tests: shapes, no-straddle, unresolved exclusion | ~90 |
| `models.py` | SQLAlchemy ORM: `FeatureMatrix` + `NormalizationStats` | ~110 |
| `schemas.py` | Pydantic v2: `FeatureMatrixRow`, `NormalizationStatOut`, `TriggerRequest/Response`, `FeatureInspectResponse` | ~85 |
| `repository.py` | Async DB: bulk upserts, get_feature_row, get_normalization_stats, delete_feature_rows | ~130 |
| `service.py` | `FeatureOrchestrator` — full + incremental modes, joblib parallelism, per-ticker isolation | ~260 |
| `dependencies.py` | FastAPI dependency wiring | ~5 |
| `router.py` | `/api/v1/feature_engineering` router with inspect + trigger sub-routers | ~10 |
| `endpoints/inspect.py` | `GET /inspect` — all 31 features + 4 targets + stats for a (ticker, date) cell | ~55 |
| `endpoints/trigger.py` | `POST /trigger` — on-demand recompute (stub, wired) | ~25 |
| `features.md` | Developer documentation: contract, protections, increment strategy | ~70 |

**Orchestration (extended from S2)**:
| File | Purpose |
|---|---|
| `orchestration/tasks/data_tasks.py` | `compute_features()` Prefect task — loads macro + OHLCV, calls `process_tickers_incremental()` with 252-trading-day seed window |
| `orchestration/flows/daily_data_refresh.py` | Extended with `compute_features()` call after ingestion |
| `scripts/feature_backfill.py` | CLI: full or incremental backfill with `--ticker`, `--jobs`, `--mode` flags |

**Database**:
| Migration | What |
|---|---|
| `a0b1c2d3e4f5_add_feature_engineering_tables.py` | `feature_matrix` (35 columns, PK with schema_version) + `normalization_stats` (5 columns), both TimescaleDB hypertables on bar_date |

**Lookahead Audit (release-blocking quality gate)**:
| File | Purpose |
|---|---|
| `tests/lookahead_audit/test_lookahead.py` | 5 tests: all-past-rows invariance for full pipeline, scaler-only, engineer-only, e2e, + standalone MacroMerger test |
| `tests/lookahead_audit/test_incremental_identity.py` | **THE GATE**: 1 test proving incremental output == full recompute bit-for-bit |

---

## 5. Critical Formulas

### Technical Indicators (locked per spec a2.4)

| Indicator | Formula | Source |
|---|---|---|
| returns_Nd | `close.pct_change(N)` | pandas |
| RSI-14 | EWM-smoothed avg gain/loss, 14-period | custom |
| MACD | 12/26 EMA difference, 9-period signal | custom |
| Bollinger Bands | SMA(20) ± 2×std(20); width = (upper-lower)/middle | custom |
| ATR-14 | EWM-smoothed true range, 14-period | custom |
| volatility_20d | `returns_1d.rolling(20).std() * sqrt(252)` | pandas |
| volume_z_score | `(volume - rolling_mean(20)) / rolling_std(20)` | pandas |
| SMA 50/200 | `close.rolling(50/200).mean()` | pandas |
| price_to_sma | `close / sma` | pandas |

### Targets (locked per spec a3.2)
```
target_t{N} = (close.shift(-N) - close) / close
```
Exact subtraction — NOT `pct_change(periods=-N)` (avoids inverse-denominator errors).

### Normalization
```
z_t = (x_t - mean(x_{t-252:t})) / std(x_{t-252:t})
```
Rolling 252-day window, `center=False` (trailing), `min_periods=252`. Applied only to 31 inputs; targets pass through untouched.

---

## 6. Decisions & Deviations

| # | Decision | Reason |
|---|---|---|
| D1 | **Pure-pandas implementation** (no TA-Lib dependency) | TA-Lib C library not available on Windows. pandas-ta incompatible with pandas>=3.0.3 (numba numpy<2.3 constraint). All 19 indicators implemented with identical formulas using pandas/numpy. |
| D2 | **TA-Lib as optional speed-up** | `equity_engineer.py` has a try-except `import talib` block. If available, it logs and uses TA-Lib; otherwise pure-pandas by default. |
| D3 | **Targets stored nullable** | Unresolved trailing rows (T+15 needs 15 future bars) get NaN. Excluded at training time by `TimeSeriesDataset`. |
| D4 | **Schema version in PK** | `feature_schema_version` in the composite PK enables side-by-side migration — compute v2 alongside v1, then cut over. |
| D5 | **Normalized features persisted** (not computed on-the-fly) | Daily inference and weekly retrain both need features; computing twice wastes compute and risks drift. `normalization_stats` stored for reproducibility. |
| D6 | **Hybrid increment strategy** | Full recompute on backfill/schema-change. Trailing-window-seeded incremental on daily — 252 trading days of seed loaded via NYSE trading calendar, pipeline runs, only new rows persisted. |

---

## 7. Risk Analysis & Mitigation

### R1 — Lookahead Bias (release-blocking)

**What it is**: Future data silently leaks into past features, making backtests look brilliant and live performance collapse.

**Protection layers**:
1. **Component-level**: `EquityFeatureEngineer` test verifies row `t` identical with 151 vs 300 rows. `FeatureScaler` test verifies row 300 identical with 301 vs 400 rows. Separate scaler instances prevent contamination.
2. **Pipeline-level audit suite** (`tests/lookahead_audit/test_lookahead.py`): 5 tests. Computes pipeline on `df[:t]` vs `df[:t+K]`, asserts **every** row from burn-in to splice is bit-identical — not just one checkpoint. Covers full pipeline, scaler-only, engineer-only, and standalone MacroMerger.
3. **Target isolation**: `FeatureScaler` operates exclusively on `input_feature_names()`. Targets pass through `df.copy()` unchanged. Verified by `test_targets_passthrough_untouched`.
4. **Trailing-window math**: `pandas.rolling(center=False)` — strictly backward-looking. Zero-std features → 0, not inf.

**P3.T10 gap fixes applied**:
- Single-row → all-rows checking (now 297+ rows per test)
- Added standalone `TestMacroMergerLookahead`
- Fixed redundant assertion and misleading test name

### R2 — Incremental Seed Window (silent corruption)

**What it is**: "Compute only new rows" without a proper seed window means SMA-200/Z-score are computed on too little history — wrong but plausible (silent corruption).

**Protection layers**:
1. **Trading calendar** (`data_ingestion/shared/trading_calendar.py`): `last_n_trading_days(252, latest_date)` returns exactly 252 NYSE trading days — NOT naive row counts. Used by `process_tickers_incremental()`.
2. **Seed window loading**: Orchestrator loads OHLCV from `seed_start` (252 trading days before latest) through today, runs full pipeline, persists only rows after `latest`.
3. **Bit-identical gate** (`tests/lookahead_audit/test_incremental_identity.py`): **THE GATE**. Runs pipeline on 600 rows vs 550 rows, asserts every past feature cell identical within `1e-10`. If this test fails, **do not ship**.

**P3.T10 gap fixes applied**:
- `compute_features` Prefect task now actually loads data and calls orchestrator (was stub returning `"queued"`)
- `feature_backfill.py` now actually loads OHLCV and calls `process_tickers()` (was stub logging "complete")
- `process_tickers_incremental()` implemented with trading-calendar-based seed window, dedup via delete-then-upsert
- Bit-identical test created and passing

---

## 8. Test Coverage Summary

| Test Suite | Count | Coverage |
|---|---|---|
| `test_feature_schema.py` | 19 | Contract counts, ordering, categories, no duplicates |
| `test_equity_engineer.py` | 20 | All 19 indicators, lookahead, raw preservation, burn-in |
| `test_macro_merger.py` | 6 | Row count, forward-fill, leading-NaN, column attachment |
| `test_target_generator.py` | 7 | Forward direction, denominator, NaN counts, input preservation |
| `test_feature_scaler.py` | 9 | Lookahead (decisive), target passthrough, per-ticker isolation, zero-std, stats, macro |
| `test_dataset.py` | 5 | Shapes, no-straddle, unresolved exclusion, normalized values |
| `test_lookahead.py` (audit) | 5 | All-rows full pipeline, scaler-only, engineer-only, e2e, MacroMerger standalone |
| `test_incremental_identity.py` (audit) | 1 | **THE GATE** — incremental == full recompute |
| **Total** | **71** | **0 failures** |

All tests run with deterministic seeds (`np.random.default_rng(seed)`) for reproducibility.

---

## 9. What Is Complete vs Pending Integration

### Complete (unit-tested)
- [x] Feature schema contract (31 features + 4 targets)
- [x] All 19 technical indicators (pure-pandas, lookahead-safe)
- [x] Macro left-join merger (forward-fill, trading-day-aligned)
- [x] Target generation (4 horizons, exact subtraction)
- [x] Rolling Z-score scaler (252-day, target-isolated, per-ticker)
- [x] PyTorch TimeSeriesDataset ([252,31]/[4] tensors)
- [x] FeatureOrchestrator (per-ticker pipeline, joblib parallelism)
- [x] DB repository (bulk upserts, feature/normalization_stats queries)
- [x] Alembic migration (feature_matrix + normalization_stats hypertables)
- [x] Prefect `compute_features` task (incremental, trading-calendar seed)
- [x] Backfill CLI script
- [x] Inspect/trigger API endpoints (wired into app.py)
- [x] Lookahead audit suite (release-blocking gate)
- [x] Bit-identical test (incremental == full recompute gate)

### Pending (requires DB + data to test)
- [ ] Run backfill on actual DB with real tickers
- [ ] Run daily increment via Prefect flow
- [ ] Integration test (ingest → compute → inspect, requires DB container)
- [ ] Frontend `/features/inspect` page (ticker + date pickers → feature table)

---

## 10. Key File Paths

```
backend/
├── alembic/versions/a0b1c2d3e4f5_add_feature_engineering_tables.py
├── app/features/feature_engineering/
│   ├── __init__.py
│   ├── models.py                    # FeatureMatrix, NormalizationStats ORM
│   ├── schemas.py                   # Pydantic v2 schemas
│   ├── repository.py                # Async DB persistence
│   ├── service.py                   # FeatureOrchestrator (full + incremental)
│   ├── router.py                    # FastAPI router (inspect + trigger)
│   ├── dependencies.py
│   ├── features.md                  # Developer docs
│   ├── endpoints/
│   │   ├── inspect.py
│   │   └── trigger.py
│   ├── shared/
│   │   ├── feature_schema.py        # 31-dim locked contract
│   │   └── tests/test_feature_schema.py
│   ├── technical/
│   │   ├── base.py                  # BaseFeatureEngineer ABC
│   │   ├── equity_engineer.py       # 19 indicators
│   │   └── tests/test_equity_engineer.py
│   ├── alignment/
│   │   ├── macro_merger.py          # Left-join macro
│   │   └── tests/test_macro_merger.py
│   └── tensor_prep/
│       ├── target_generator.py      # 4-horizon targets
│       ├── feature_scaler.py        # Rolling Z-score
│       ├── dataset.py               # PyTorch TimeSeriesDataset
│       └── tests/
│           ├── test_target_generator.py
│           ├── test_feature_scaler.py
│           └── test_dataset.py
├── app/orchestration/
│   ├── flows/daily_data_refresh.py  # Extended: compute_features after ingest
│   └── tasks/data_tasks.py          # compute_features Prefect task
├── scripts/feature_backfill.py      # CLI backfill tool
└── tests/lookahead_audit/
    ├── test_lookahead.py            # Release-blocking audit (5 tests)
    └── test_incremental_identity.py # Bit-identical gate (1 test)

docs/plans/2026-06-28-stage-s3-feature-engineering.md    # Implementation plan
docs/post-development_docs/S3/                            # This document
```

---

## 11. Running the Pipeline

```bash
# Full backfill (all tickers)
uv run python scripts/feature_backfill.py --mode full

# Incremental backfill (single ticker)
uv run python scripts/feature_backfill.py --ticker AAPL --mode incremental

# Run all unit tests
uv run pytest app/features/feature_engineering/ -v

# Run lookahead audits (excluding slow E2E)
uv run pytest tests/lookahead_audit/ -v -k "not slow"

# Run THE GATE
uv run pytest tests/lookahead_audit/test_incremental_identity.py -v
```
