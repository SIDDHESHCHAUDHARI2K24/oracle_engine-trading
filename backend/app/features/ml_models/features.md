# ML Models — Blocks A4 + A5 + A6

## Overview

Trains, calibrates, blends, and scores ML models per universe. Each universe
gets a Bi-LSTM global model plus four TFTs (one per forecast horizon). A
conformal calibrator wraps the ensemble to produce well-calibrated prediction
intervals, and a conviction scorer rates each forecast on a 0–100 scale.

## Architecture

```
┌──────────────┐    ┌───────────────────────────────┐
│ Feature      │───▶│  Bi-LSTM                       │
│ Tensor       │    │  3-layer, bidirectional,       │
│ [252×31]     │    │  attention → [256,64,4]        │
│              │    └───────────────┬───────────────┘
│              │                    │ lstm_outputs [N×4]
│              │    ┌───────────────▼───────────────┐
│              │───▶│  TFT Quad-Array                │
│              │    │  t1 / t5 / t10 / t15 per model │
│              │    │  ticker_id = static covariate   │
│              │    └───────────────┬───────────────┘
│              │                    │ q10, q50, q90 [N×4]
│              │    ┌───────────────▼───────────────┐
│              │    │  RegimeBlender                  │
│              │    │  Uncertainty-aware weighting    │
│              │    │  lstm_w ∈ [0.40, 0.80]         │
│              │    └───────────────┬───────────────┘
│              │                    │ blended [N×4]
│              │    ┌───────────────▼───────────────┐
│              │───▶│  ConformalCalibrator            │
│              │    │  ResidualPredictor [31→16→8→1] │
│              │    │  Per-horizon quantiles          │
│              │    └───────────────┬───────────────┘
│              │                    │ lo, hi [N×4]
│              │    ┌───────────────▼───────────────┐
│              │    │  ConvictionScorer               │
│              │    │  z = pred / sigma  →  [0,100]  │
│              │    └───────────────────────────────┘
└──────────────┘
```

Flow: 31-dim features → LSTM + 4 TFTs → blend → calibrate → score.

## 3-Way Walk-Forward Split (70/15/15)

Within each rolling 2-year training window, dates are partitioned
strictly chronologically:

| Split | Fraction | Purpose |
|---|---|---|
| Train | 70% | Weight updates, gradient descent |
| Calibration | 15% | Compute conformal non-conformity scores |
| Validation | 15% | Early-stopping signal, held-out metrics |

Random shuffling is forbidden. The calibration and validation sets always
follow the training set in time with no overlap. Weekly retraining slides the
entire window forward by 7 trading days.

Implementation: `shared/walk_forward.py` — `create_walk_forward_split()`
and `slide_window_forward()`.

## Model Roles & 7 Artifacts Per Universe

Each universe produces exactly 7 artifacts stored in the artifact store:

| # | Role | Description |
|---|---|---|
| 1 | `lstm` | Bi-LSTM global ticker-agnostic model |
| 2 | `tft_t1` | TFT for T+1 horizon |
| 3 | `tft_t5` | TFT for T+5 horizon |
| 4 | `tft_t10` | TFT for T+10 horizon |
| 5 | `tft_t15` | TFT for T+15 horizon |
| 6 | `conformal` | Calibrated ConformalCalibrator (quantiles + residual predictor state) |
| 7 | `residual_predictor` | Standalone ResidualPredictor weights |

Artifact lifecycle is managed by `ArtifactLifecycleService` — uploaded after
training, activated on promotion, archived on replacement.

## Champion / Challenger Promotion Protocol

Every training run produces a challenger set of 7 artifacts. The promotion
logic in `promotion.py`:

1. **No champion exists** → auto-promote challenger.
2. **Champion exists** → compare `overall_mse` on the validation split.
3. Relative improvement = `(champion_mse - challenger_mse) / champion_mse`.
4. If improvement ≥ `promotion_margin` (default 2%) → activate challenger,
   archive champion.
5. Otherwise → discard challenger, champion stays.

The promotion margin is configurable. This prevents thrashing from noisy
validation metrics.

## Conformal Calibration — Locally-Weighted Split Conformal

`conformal/calibrator.py` (~180 lines):

1. **ResidualPredictor**: A small MLP `[31 → 16 → 8 → 1]` with ReLU,
   Dropout(0.1), and Softplus output. Trained to predict expected absolute
   residual magnitude from the 31-dim feature vector. This captures
   heteroskedasticity — forecasts are less certain when features are volatile.

2. **Calibration**: On the held-out 15% calibration split:
   - Compute raw residuals `r = |y_true - y_pred|`
   - Train ResidualPredictor on (features, mean_residual) pairs
   - Compute predicted residuals `r_hat = ResidualPredictor(features)`
   - For each horizon h: `q_h = quantile(r_h / r_hat, 1 - alpha)`

3. **Inference**: For new features x and blended prediction y:
   - `r_hat = ResidualPredictor(x)`
   - `lo_h = y_h - q_h * r_hat`
   - `hi_h = y_h + q_h * r_hat`

Default `alpha = 0.10` → 90% target coverage.

## Residual Predictor Architecture

```
Linear(31, 16) → ReLU → Dropout(0.1)
  → Linear(16, 8) → ReLU → Dropout(0.1)
  → Linear(8, 1) → Softplus
```

Trained for 200 epochs with Adam(lr=1e-3) and early-stopping patience of 20.
The Softplus output ensures `r_hat > 0`, avoiding division by zero in score
normalization.

## Ensemble Blending — Uncertainty-Aware

`ensemble/blender.py` — `RegimeBlender`:

```
tft_spread = tft_q90 - tft_q10
spread_z   = rolling_z_score(tft_spread, window=200)
lstm_w     = clip(base_lstm_w + 0.10 × spread_z, 0.40, 0.80)
blended    = lstm_pred × lstm_w + tft_q50 × (1 - lstm_w)
```

When TFT uncertainty is high (wide quantile spread), the blender leans toward
the LSTM. `base_lstm_w` defaults to 0.60.

## Conviction Score — Derivation A

`ensemble/scoring.py`:

```
sigma   = (tft_q90 - tft_q10) / 2.563     # 10-90 spread → approx 1σ
z       = y_pred / (sigma + 1e-9)          # risk-adjusted magnitude
score   = clip(z × 25 + 50, 0, 100)       # linear map, centered at 50
```

| Score Range | Interpretation |
|---|---|
| 70–100 | Strong bullish conviction |
| 55–70  | Mild bullish |
| 45–55  | Neutral |
| 0–45   | Bearish (not emitted in v1 long-only) |

The divisor 2.563 maps the 10–90 percentile range of a standard normal to
approximately 1σ. The scaling factor 25 keeps scores in a readable 0–100 band.

## Conformal Coverage Tracking

`conformal/coverage_tracker.py`:

- **`compute_realized_coverage()`**: Fraction of actual outcomes that fell
  within `[pred_lo, pred_hi]` across all horizons. NaN if no valid pairs.
- **`compute_rolling_coverage()`**: Sliding-window coverage (default 30 rows).
  Returns list of (date, coverage) pairs.
- **`check_breach()`**: If the last N periods all fall below threshold
  (default 0.80 for N=5), the calibrator has degraded and a retrain is recommended.

## Portable Training Callable + Colab Workflow

The training pipeline in `service.py` (`run_lstm_training` and related
functions) is designed to work in two environments:

1. **Prefect orchestrated**: Invoked by scheduled flows with DB session
   injection and artifact-store wiring.
2. **Google Colab / standalone**: Importable with a local artifact store
   (`LocalArtifactStore`). No DB required — pass features as NumPy arrays
   and receive `TrainingResult` with artifact paths.

The `LocalArtifactStore` writes to a filesystem directory instead of S3,
enabling offline iterative research.

## Key Formulas Summary

| Formula | Location | Description |
|---|---|---|
| Walk-forward split | `shared/walk_forward.py:6` | `train[:70%], cal[70%:85%], val[85%:]` |
| Blend weight | `ensemble/blender.py:30` | `lstm_w = clip(base + 0.10×z, 0.40, 0.80)` |
| Conviction score | `ensemble/scoring.py:12` | `z = y_pred/σ; score = clip(z×25+50, 0, 100)` |
| Conformal interval | `conformal/calibrator.py:177` | `[ŷ - q·r̂, ŷ + q·r̂]` |
| Promotion gate | `promotion.py:76` | `(champion - challenger)/champion ≥ margin` |
| σ from spread | `ensemble/scoring.py:9` | `σ = (q90 - q10) / 2.563` |

## Tables

- `training_runs`: One row per training invocation. Records window bounds,
  hyperparams snapshot, validation metrics, status, and error summary.
- `model_artifacts`: One row per artifact file. Linked to `training_run_id`
  and `universe_id`. Tracks model role, path, size, and active flag.
- `inference_runs`: One row per inference invocation. Records date, status,
  artifact IDs used, and ticker counts.
- `predictions`: TimescaleDB-partitioned on `inference_date`. One row per
  ticker per inference date with all 4 horizons × 4 fields (pred, lo, hi,
  conviction) plus raw model outputs. Duplicate-safe via unique constraint
  on `(ticker_id, universe_id, inference_date)`.

## Directory Structure

```
ml_models/
├── __init__.py
├── features.md                  ← this file
├── models.py                    # SQLAlchemy models
├── schemas.py                   # Pydantic schemas
├── repository.py                # Data access layer
├── service.py                   # Training orchestrator + portable callable
├── inference_service.py         # Inference pipeline
├── artifact_service.py          # Artifact lifecycle (upload/activate/archive)
├── promotion.py                 # Champion/challenger promotion logic
├── router.py                    # FastAPI router
├── dependencies.py              # FastAPI dependency injection
├── shared/
│   ├── __init__.py
│   ├── base.py                  # Shared base classes / utilities
│   └── walk_forward.py          # 3-way split + slide window
├── lstm/
│   ├── __init__.py
│   ├── architecture.py          # Bi-LSTM model definition
│   └── trainer.py               # Training loop with Lightning
├── tft/
│   ├── __init__.py
│   ├── architecture.py          # TFT model definition
│   └── data_adapter.py          # pytorch-forecasting bridge
├── ensemble/
│   ├── __init__.py
│   ├── blender.py               # RegimeBlender
│   ├── scoring.py               # Conviction score computation
│   └── orchestrator.py          # EnsembleOrchestrator
├── conformal/
│   ├── __init__.py
│   ├── calibrator.py            # ConformalCalibrator + ResidualPredictor
│   └── coverage_tracker.py      # Realized/rolling coverage + breach detection
├── endpoints/
│   ├── __init__.py
│   └── model_health.py          # Health-check endpoints
└── tests/
    ├── test_inference.py
    ├── test_training_pipeline.py
    ├── lstm/
    ├── tft/
    ├── ensemble/
    └── conformal/
```

## Quality Gates

1. **Walk-forward audit**: All test dates strictly chronologically ordered
   with zero overlap across splits.
2. **Conformal coverage**: Held-out test coverage must fall within
   `[1-α - 0.03, 1-α + 0.03]` (e.g. [0.87, 0.93] for α=0.10).
3. **Promotion margin**: Challenger must beat champion by ≥ 2% on validation
   MSE before activation.
4. **Breach monitoring**: Rolling coverage below 0.80 for 5+ consecutive
   periods triggers a retrain recommendation.
5. **Bit-identical reproducibility**: Fixed seeds on all random generators
   (torch + numpy + random). Tests assert deterministic outputs.
