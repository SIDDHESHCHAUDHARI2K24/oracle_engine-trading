# Feature Engineering — Blocks A2 + A3

## Overview

Transforms raw OHLCV + macro data from the data ingestion pipeline into
the **31-dimensional feature tensor** consumed by the ML models (Bi-LSTM + TFT).

## 31-Dimensional Contract

The feature matrix consists of exactly **31 input features**:
- **5 raw**: open, high, low, close, volume (untouched from Block A1)
- **19 technical**: returns_{1d,5d,10d,20d}, rsi_14, macd, macd_signal, macd_hist,
  bb_{upper,middle,lower}, bb_width, atr_14, volatility_20d, volume_z_score,
  sma_{50,200}, price_to_sma{50,200}
- **7 macro**: fed_funds_rate, cpi, unemployment, gdp, yield_spread_10y_2y, vix, high_yield_spread

Plus **4 targets**: target_t1, target_t5, target_t10, target_t15 (continuous forward returns).

The schema is locked in `shared/feature_schema.py`. Any change requires a
documented deviation + schema-version bump.

## Lookahead Protections

| Protection | Mechanism |
|---|---|
| No future data in features | All calculations use trailing-window only. Asserted via test fixtures. |
| Targets isolated from features | FeatureScaler operates exclusively on 31 input columns. Targets pass through untouched. |
| Rolling Z-score normalization | Uses only trailing 252 days: z_t = (x_t - mean(x_{t-252:t})) / std(x_{t-252:t}) |
| Per-ticker scaling | Each ticker normalized in isolation. No cross-ticker leakage. |

## Hybrid Increment Strategy

- **Full recompute**: On backfill or schema change. All tickers, all history, parallelized via joblib.
- **Incremental**: Daily Prefect flow. Loads trailing 252-day seed window per ticker using the
  trading calendar (not naive row counts), runs full pipeline, writes only new rows.
- **Bit-identical test**: Incremental output must match full recompute for the same dates
  within float tolerance. This is the gate that prevents silent indicator corruption.

## Component Map

| Sub-feature | File | Purpose |
|---|---|---|
| Feature schema | `shared/feature_schema.py` | Locked 31-column contract |
| Technical engineer | `technical/equity_engineer.py` | 19 indicators, pure-pandas |
| Macro merger | `alignment/macro_merger.py` | Left-join forward-filled macro |
| Target generator | `tensor_prep/target_generator.py` | 4-horizon continuous returns |
| Feature scaler | `tensor_prep/feature_scaler.py` | Rolling 252-day Z-score |
| Dataset | `tensor_prep/dataset.py` | PyTorch [252,31]/[4] tensors |
| Orchestrator | `service.py` | Per-ticker pipeline + joblib parallelism |
| Repository | `repository.py` | TimescaleDB bulk upserts |
| API | `endpoints/{trigger,inspect}.py` | Trigger compute, inspect features |

## Tables

- `feature_matrix`: TimescaleDB hypertable on bar_date. PK: (ticker_id, bar_date, feature_schema_version).
  Enables schema-versioned migrations (compute v2 alongside v1, then cut over).
- `normalization_stats`: TimescaleDB hypertable on bar_date. PK: (ticker_id, bar_date, feature_name).
  Stores rolling mean/std per feature per ticker per day for reproducibility.

## Quality Gates

1. **Lookahead audit suite** (`tests/lookahead_audit/`): Release-blocking. Computes full pipeline
   on history[:t] vs history[:t+K] and asserts all past features identical.
2. **Bit-identical test** (P3.T8.S3): Incremental output must match full recompute.
3. **Feature schema tests**: 19 tests verifying the 31-column contract.
4. **Scaler tests**: 9 tests including the decisive lookahead-leakage test.
