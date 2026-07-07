# Stage S4 — ML Models (Blocks A4 + A5 + A6) — Implementation Plan

> **Date**: 2026-06-28
> **Status**: Ready for execution
> **Source**: `features-to-develop/development-plan-S4.md`, `docs/mbi-pipeline-a-v1-design.md` §6
> **Previous**: S3 — Feature Engineering (complete, 71 tests passing)
> **Next**: S5 — Backtesting (A7) + Conviction Tickets (A8)

---

## 0. Pre-Flight: Codebase Context & Path Corrections

### Correct File Paths

The AGENTS.md references `backend/src/backend/features/` but actual code lives in `backend/app/features/`. All S4 work uses:

```
backend/app/features/ml_models/       ← NEW (create all S4 code here)
backend/app/core/services/            ← torch_device.py goes alongside artifact_store.py
backend/alembic/versions/             ← New migration for ML tables
backend/app/orchestration/flows/      ← New weekly_retrain.py + daily_inference.py
frontend/src/features/model_health/   ← NEW (T12.S2 frontend)
```

### Builds On

| Dependency | Path | Key Interface |
|---|---|---|
| S3 TimeSeriesDataset | `app/features/feature_engineering/tensor_prep/dataset.py` | `TimeSeriesDataset(rows) -> (X:[252,31], y:[4])` |
| S3 feature_matrix | `app/features/feature_engineering/models.py` | `FeatureMatrix` ORM with 31 features + 4 targets |
| S0 artifact store | `app/core/services/artifact_store.py` | `ArtifactStore` Protocol (put/get/exists/delete/list) |
| S0 DB fixtures | `app/features/conftest.py` | `database_url` + `db_session` (testcontainers) |
| S2 Prefect infra | `app/orchestration/` | `deployments.py`, daily_data_refresh flow |

### Test Patterns to Follow

- Async DB tests: `@pytest.mark.asyncio` + `db_session` fixture (transactions roll back)
- HTTP integration: `httpx.AsyncClient(transport=ASGITransport(app=app))` + `dependency_overrides`
- Pure math/model tests: synchronous + synthetic data + no DB
- Mocking: `pytest.monkeypatch.setattr("full.dotted.path", lambda: ...)`, NOT `unittest.mock`
- DB container: session-scoped `testcontainers.postgres.PostgresContainer` (TimescaleDB image)

### Dependencies Available

```toml
# In pyproject.toml (needs additions)
"torch>=2.2.0",          # ✓ already present
"scipy>=1.11.0",         # ✓ already present (conformal quantiles)
"tenacity>=9.1.4",       # ✓ retry logic
# NEED TO ADD:
"pytorch-lightning>=2.1.0,<3.0",
"pytorch-forecasting>=1.0.0,<2.0",
```

---

## Dependency Map (Updated with Gaps)

```
S3 (complete) ──> P4.T0 (S3→S4 verification) ──> ALL tasks
                        │
         ┌──────────────┼──────────────┬──────────────┐
         ▼              ▼              ▼              ▼
      P4.T1           P4.T2          P4.T3          P4.T5
    (schema +       (3-way split   (LSTM arch)    (TFT adapter)
    artifacts)      + GPU device)      │              │
         │              │              ▼              ▼
         │              ├────────> P4.T4 (LSTM trainer)
         │              │              │
         │              ├────────> P4.T6 (conformal)──┐
         │              │              │               │
         └──────────────┴──────────────┴───────────────┤
                                                       ▼
                                                  P4.T7 (blender)
                                                       │
                                                       ▼
                                                  P4.T8 (orchestrator)
                                                       │
                              ┌────────────────────────┤
                              ▼                        ▼
                           P4.T9 (training        P4.T13 (residual
                           pipeline + champ)     predictor dims +
                                                 checkpointing)
                              │                        
                    ┌─────────┼─────────┐              
                    ▼         ▼         ▼              
                 P4.T10   P4.T11    P4.T12            
               (inference) (Prefect) (UI + E2E)        
```

### Parallel Work Streams

| Stream | Tasks | Can run concurrently with |
|---|---|---|
| Infrastructure | T0, T1, T2 | Each other + model work |
| LSTM track | T3 → T4 | TFT track |
| TFT track | T5 | LSTM track |
| Conformal track | T6 | LSTM + TFT (needs T2 only) |
| Integration track | T7 → T8 → T9 → T10 → T11 → T12 | Sequential, depends on all above |

**Critical path**: T2 → T4 → T7 → T8 → T9 → T10 → T11 → T12

---

## P4.T0: S3→S4 Integration Verification [NEW — Gap 1]

**Effort**: S / 2 hrs
**Dependencies**: S3
**Risk Level**: Low

### Purpose
Verify that the S3 `TimeSeriesDataset` integrates correctly with PyTorch DataLoader patterns the ML models will consume. Catch any tensor shape, dtype, or NaN issues before building models.

### Checklist
- [ ] **T0.1**: Verify `TimeSeriesDataset` returns `float32` tensors (not `float64`)
- [ ] **T0.2**: Verify NaN targets are excluded by the `__len__` / `__getitem__` contract
- [ ] **T0.3**: Verify `DataLoader(ds, batch_size=256)` yields correct shapes `[B,252,31]` and `[B,4]`
- [ ] **T0.4**: Verify tensor ordering matches `feature_schema.py` column order
- [ ] **T0.5**: Verify data on GPU with `.to(device)` works (if CUDA/MPS available)
- [ ] **T0.6**: Create `backend/app/features/ml_models/__init__.py`
- [ ] **T0.7**: Add `pytorch-lightning>=2.1.0,<3.0` and `pytorch-forecasting>=1.0.0,<2.0` to `pyproject.toml`

### File to Create
- `backend/app/features/ml_models/__init__.py` → empty (feature package marker)
- `backend/app/features/ml_models/tests/test_s3_integration.py` → verification tests

### Acceptance Criteria
- [ ] DataLoader from TimeSeriesDataset produces expected tensor shapes
- [ ] Model can receive a batch and run `.to(device)`
- [ ] New deps install cleanly via `uv sync`

---

## P4.T1: ML Schema + Artifact Management

**Effort**: M / 1 day
**Dependencies**: S3, S0
**Risk Level**: Low

### T1.S1: Define ORM Models [~4 hrs]

Create `backend/app/features/ml_models/models.py` with four ORM models exactly per design §6:

```python
# training_runs — one per training execution
class TrainingRun(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "training_runs"
    universe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universes.id"), nullable=False)
    triggered_by: Mapped[str]  # ENUM: weekly_scheduled, on_demand, cold_start
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    status: Mapped[str]  # ENUM: running, succeeded, failed
    train_window_start: Mapped[date | None]
    train_window_end: Mapped[date | None]
    calibration_window_start: Mapped[date | None]
    calibration_window_end: Mapped[date | None]
    validation_window_start: Mapped[date | None]
    validation_window_end: Mapped[date | None]
    num_tickers: Mapped[int | None]
    num_training_samples: Mapped[int | None]
    hyperparams_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_summary: Mapped[str | None]
    metadata: Mapped[dict] = mapped_column(JSONB, default={})

# model_artifacts — one per (universe, role), only one active at a time
class ModelArtifact(Base, UUIDPrimaryKey):
    __tablename__ = "model_artifacts"
    universe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universes.id"), nullable=False)
    training_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("training_runs.id"), nullable=False)
    model_role: Mapped[str]  # ENUM: lstm, tft_t1, tft_t5, tft_t10, tft_t15, conformal, residual_predictor
    artifact_path: Mapped[str]
    size_bytes: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(default=False)
    metadata: Mapped[dict] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    archived_at: Mapped[datetime | None]

# inference_runs — one per daily inference execution per universe
class InferenceRun(Base, UUIDPrimaryKey):
    __tablename__ = "inference_runs"
    universe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universes.id"), nullable=False)
    triggered_by: Mapped[str]  # ENUM: daily_scheduled, on_demand
    inference_date: Mapped[date]
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    status: Mapped[str]  # ENUM: running, succeeded, failed
    artifact_ids: Mapped[list] = mapped_column(JSONB, default=[])  # which 7 artifacts used
    num_tickers_scored: Mapped[int | None]
    error_summary: Mapped[str | None]

# predictions — per ticker per inference_date, TimescaleDB hypertable
class Prediction(Base, UUIDPrimaryKey):
    __tablename__ = "predictions"
    inference_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inference_runs.id"), nullable=False)
    ticker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    universe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universes.id"), nullable=False)
    inference_date: Mapped[date]
    # 4 horizons × (point, lo, hi, conviction)
    pred_t1: Mapped[float]; pred_lo_t1: Mapped[float]; pred_hi_t1: Mapped[float]; conviction_t1: Mapped[float]
    pred_t5: Mapped[float]; pred_lo_t5: Mapped[float]; pred_hi_t5: Mapped[float]; conviction_t5: Mapped[float]
    pred_t10: Mapped[float]; pred_lo_t10: Mapped[float]; pred_hi_t10: Mapped[float]; conviction_t10: Mapped[float]
    pred_t15: Mapped[float]; pred_lo_t15: Mapped[float]; pred_hi_t15: Mapped[float]; conviction_t15: Mapped[float]
    # raw component outputs
    lstm_outputs: Mapped[list] = mapped_column(ARRAY(Float))  # length 4
    tft_q10: Mapped[list] = mapped_column(ARRAY(Float))       # length 4
    tft_q50: Mapped[list] = mapped_column(ARRAY(Float))       # length 4
    tft_q90: Mapped[list] = mapped_column(ARRAY(Float))       # length 4
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    __table_args__ = (UniqueConstraint("ticker_id", "universe_id", "inference_date"),)
```

### T1.S2: Author Migration [~3 hrs]

Create `backend/alembic/versions/XXXX_add_ml_model_tables.py`:
- Create all 4 tables
- Convert `predictions` to hypertable on `inference_date`
- Champion partial-unique index: `CREATE UNIQUE INDEX ix_model_artifacts_active ON model_artifacts (universe_id, model_role) WHERE is_active = true`
- Design indexes: `(universe_id, started_at DESC)` on training_runs, `(universe_id, model_role, created_at DESC)` on artifacts, `(universe_id, inference_date DESC)` and `(ticker_id, inference_date DESC)` on predictions

### T1.S3: Artifact Lifecycle Service [~4 hrs]

Create `backend/app/features/ml_models/artifact_service.py`:
- `save_artifact(universe_id, role, training_run_id, bytes) -> ModelArtifact` — writes file via artifact_store + DB row (inactive)
- `activate(artifact_id)` — atomic champion swap (SELECT FOR UPDATE, deactivate old, activate new, commit)
- `load_active(universe_id, role) -> bytes` — loads active artifact's bytes from store
- `archive_old(cutoff_date)` — marks artifacts older than cutoff as archived
- Path format: `{universe.slug}/{role}/{training_run_id}.pt`

### Files to Create
- `backend/app/features/ml_models/models.py`
- `backend/app/features/ml_models/schemas.py` (Pydantic v2 schemas for all 4 tables)
- `backend/app/features/ml_models/artifact_service.py`
- `backend/app/features/ml_models/repository.py` (DB queries for training_runs, artifacts, inference_runs, predictions)
- `backend/alembic/versions/XXXX_add_ml_model_tables.py`

### Acceptance Criteria
- [ ] Four models match design §6 column-for-column
- [ ] `model_role` enum has all 7 roles; partial-unique index enforced
- [ ] `predictions` registered as a hypertable
- [ ] Migration `upgrade`/`downgrade` round-trip clean
- [ ] `Activate` atomically swaps champion (never 0 or 2 active for a role)

---

## P4.T2: Walk-Forward Split + GPU Device Routing

**Effort**: M / 1 day
**Dependencies**: S3
**Risk Level**: Medium

### T2.S1: 3-Way Walk-Forward Split [~4 hrs]

Create `backend/app/features/ml_models/shared/walk_forward.py`:
- `create_walk_forward_split(dates: list[date]) -> tuple[set[date], set[date], set[date]]`
- Strictly chronological: sort by date → slice 0-70%, 70-85%, 85-100%
- No random shuffling
- Returns concrete date ranges for storing on `training_runs`
- `slide_window_forward(dates, trading_days=7) -> list[date]` for weekly retrain
- Assertions: calibration dates > train dates; validation dates > calibration dates
- Unit test: `test_walk_forward.py` — test chronological order, leakage check, 70/15/15 ratio

### T2.S2: GPU Device Routing + Reproducibility [~3 hrs]

Create `backend/app/core/services/torch_device.py`:
```python
import torch
import random
import numpy as np

def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # NOTE: torch.use_deterministic_algorithms(True) may break TFT on CUDA
```

### Files to Create
- `backend/app/features/ml_models/shared/__init__.py`
- `backend/app/features/ml_models/shared/walk_forward.py`
- `backend/app/features/ml_models/shared/tests/test_walk_forward.py`
- `backend/app/core/services/torch_device.py`

### Acceptance Criteria
- [ ] 70/15/15 chronological split; no shuffling
- [ ] Calibration and validation strictly follow training in time
- [ ] Date bounds returned and recorded on training run
- [ ] Device routing prefers cuda, then mps, then cpu; logged
- [ ] Seed helper makes training reproducible on CPU

---

## P4.T3: LSTM Architecture (Block A4.1)

**Effort**: M / 1 day
**Dependencies**: S3
**Risk Level**: Low

### T3.S1: BaseMathEngine ABC [~2 hrs]

Create `backend/app/features/ml_models/shared/base.py`:
```python
from abc import ABC, abstractmethod
class BaseMathEngine(ABC):
    @abstractmethod
    def train_model(self, train_loader, val_loader) -> None: ...
    @abstractmethod
    def predict(self, x: torch.Tensor) -> np.ndarray: ...
    def serialize(self) -> bytes: ...
    @classmethod
    def deserialize(cls, data: bytes) -> "BaseMathEngine": ...
```

### T3.S2: LSTMMathEngine Architecture [~4 hrs]

Create `backend/app/features/ml_models/lstm/architecture.py`:
- Exactly per design §6: Bi-LSTM(31, 128, 3 layers, bidirectional) → MultiheadAttention(256, 8 heads) → Linear(256,64) → ReLU → Dropout(0.3) → Linear(64,4)
- **NO Sigmoid** (locked deviation #1)
- Ticker-agnostic: no ticker embedding
- Forward pass on `[B,252,31]` yields `[B,4]` unbounded continuous returns
- Attention pooling: mean-pool over sequence dimension (documented choice)
- Implement `BaseMathEngine`

### Files to Create
- `backend/app/features/ml_models/shared/base.py`
- `backend/app/features/ml_models/lstm/__init__.py`
- `backend/app/features/ml_models/lstm/architecture.py`
- `backend/app/features/ml_models/lstm/tests/test_architecture.py`

### Acceptance Criteria
- [ ] Architecture matches design §6 exactly (no Sigmoid)
- [ ] Forward pass on `[B,252,31]` yields `[B,4]`
- [ ] No ticker embedding (ticker-agnostic confirmed)

---

## P4.T4: LSTM Trainer (Block A4.2)

**Effort**: L / 2 days
**Dependencies**: P4.T3, P4.T2
**Risk Level**: Medium

### T4.S1: LSTM Trainer Tests (TDD — RED first) [~4 hrs]

Create `backend/app/features/ml_models/lstm/tests/test_lstm_trainer.py`:
- Test 1: Walk-forward split is used (verify no shuffling)
- Test 2: HuberLoss is the objective function
- Test 3: Early stopping halts after 10 no-improve epochs, restores best weights
- Test 4: ReduceLROnPlateau fires on plateau (verify LR decreases)
- Test 5: Trained `predict` returns `[N,4]` shape
- Test 6: Training uses only 70% train slice + 15% validation slice (calibration excluded)
- Use synthetic data with learnable signal so loss visibly drops
- Shrink epochs (e.g., max_epochs=5) for fast tests

### T4.S2: LSTMTrainer Implementation [~1 day]

Create `backend/app/features/ml_models/lstm/trainer.py`:
- Custom PyTorch loop (per locked decision)
- AdamW(lr=1e-3, weight_decay=1e-4)
- HuberLoss (reduction='mean')
- ReduceLROnPlateau(patience=5, factor=0.5)
- Early stopping: halt after 10 no-improve epochs, restore best weights
- Max 100 epochs, batch size 256
- Per-epoch loss history captured for dashboard
- Implements `BaseMathEngine.train_model()`

### T4.S3: LSTM Inference Helper [~3 hrs]

Create `backend/app/features/ml_models/lstm/inference.py`:
- `load_lstm(path) -> LSTMMathEngine` — deserialize from artifact bytes
- `run_lstm_inference(model, dataloader) -> np.ndarray` — batched forward pass in eval mode
- Returns `[N,4]` numpy array per BaseMathEngine contract

### Files to Create
- `backend/app/features/ml_models/lstm/trainer.py`
- `backend/app/features/ml_models/lstm/inference.py`
- `backend/app/features/ml_models/lstm/tests/test_lstm_trainer.py`

### Acceptance Criteria
- [ ] All T4.S1 tests pass (RED → GREEN)
- [ ] Hyperparameters match spec exactly
- [ ] Trains on 70%, validates on 15% (calibration 15% unused in LSTM training)
- [ ] Per-epoch loss history captured

---

## P4.T5: TFT Quad-Array (Block A5)

**Effort**: XL / 3 days
**Dependencies**: P4.T2, S3
**Risk Level**: High

### T5.S1: pytorch-forecasting TimeSeriesDataSet Adapter [~1 day] [HIGH RISK]

Create `backend/app/features/ml_models/tft/data_adapter.py`:
- Map `feature_matrix` DataFrame → pytorch-forecasting `TimeSeriesDataSet`
- `time_idx`: contiguous integer per ticker group (handle trading calendar gaps by mapping dates → sequential indices)
- `group_ids`: ticker_id as static categorical
- Time-varying knowns: 7 macro features
- Time-varying unknowns: 5 raw + 19 technical features
- Static categoricals: ticker_id
- One dataset per horizon (target_t1, target_t5, target_t10, target_t15)
- Respect walk-forward split boundaries

**Risk flags**: `time_idx` must be contiguous per group — trading calendar gaps need special handling. Allocate spike time here.

### T5.S2: TemporalFusionQuadArray Architecture [~1 day]

Create `backend/app/features/ml_models/tft/architecture.py`:
- `TemporalFusionQuadArray` — wraps 4 `TemporalFusionTransformer` instances
- Each TFT: `from_dataset(dataset, loss=QuantileLoss([0.1,0.5,0.9]), ...)`
- Asset-aware via ticker_id static covariate
- Implements `BaseMathEngine`
- Output per horizon: `{q10, q50, q90}`

### T5.S3: TFT Trainer + Inference [~1 day]

Create `backend/app/features/ml_models/tft/trainer.py`:
- 4 PyTorch Lightning `Trainer` instances (one per horizon)
- `EarlyStopping(monitor='val_loss', patience=10)` + `LearningRateMonitor()`
- Device-routed via `get_device()`
- Sequential training (simpler) or parallel if GPU memory allows
- Capture per-horizon val loss for dashboard

Create `backend/app/features/ml_models/tft/inference.py`:
- `run_tft_inference(model, dataloader) -> dict` — returns `{q10, q50, q90}` per horizon
- Uses `model.predict(dataloader, mode='quantiles')`

### Files to Create
- `backend/app/features/ml_models/tft/__init__.py`
- `backend/app/features/ml_models/tft/data_adapter.py`
- `backend/app/features/ml_models/tft/architecture.py`
- `backend/app/features/ml_models/tft/trainer.py`
- `backend/app/features/ml_models/tft/inference.py`
- `backend/app/features/ml_models/tft/tests/test_data_adapter.py`

### Acceptance Criteria
- [ ] `TimeSeriesDataSet` builds with correct covariate typing
- [ ] One dataset per horizon; contiguous `time_idx` handled
- [ ] 4 TFTs instantiated with QuantileLoss; ticker as static covariate
- [ ] Training via Lightning with early stopping; inference returns q10/q50/q90
- [ ] Colab fallback documented in tft module docstring

---

## P4.T6: Conformal Calibrator (Block A6.2)

**Effort**: L / 2 days
**Dependencies**: P4.T2
**Risk Level**: High

### T6.S1: Conformal Tests (TDD — RED first) [~4 hrs]

Create `backend/app/features/ml_models/conformal/tests/test_calibrator.py`:
- Test 1: On synthetic data with known noise, calibrated intervals achieve ~90% empirical coverage
- Test 2: Intervals widen with local volatility (higher noise region → wider interval)
- Test 3: Calibration set strictly separate from training (overlap assertion)
- Test 4: Coverage on held-out test split is within ±3% of nominal 90%
- Test 5: Zero r_hat edge case handled (epsilon division)
- Test 6: Residual predictor MLP trains and reduces below baseline

### T6.S2: ConformalCalibrator + Residual Predictor [~1 day]

Create `backend/app/features/ml_models/conformal/calibrator.py`:
```python
class ResidualPredictor:
    """Small MLP: features -> expected |residual|. [NEW - Gap 5: pinned dims]"""
    def __init__(self):
        self.model = nn.Sequential(
            nn.Linear(31, 16),  # input_dim=31 (all features)
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(8, 1),    # output: expected |residual|
            nn.Softplus(),       # ensures positive output
        )
```

`ConformalCalibrator` (~120 lines):
- `fit(blended_model, calibration_loader)`:
  1. Generate predictions on calibration slice
  2. Train residual_predictor on (features → |residual|)
  3. Compute s_i = |y_true - y_pred| / (r_hat_i + eps)
  4. Store q = (1-α) quantile of s_i per horizon
- `predict(y_pred, features) -> tuple[lo, hi]`:
  `r_hat = residual_predictor(features)`
  `interval = [y_pred - q*r_hat, y_pred + q*r_hat]`
- **Assertion**: calibration indices never overlap training indices
- Fit ONLY on 15% calibration slice (never training data)

### T6.S3: Coverage Tracker [~3 hrs]

Create `backend/app/features/ml_models/conformal/coverage_tracker.py`:
- `compute_realized_coverage(predictions, actuals) -> float`
- Rolling window (30/90 days) coverage computation
- Flag breaches: <80% sustained for 90% target intervals
- Output ready for `coverage_metrics` table (S6)

### Files to Create
- `backend/app/features/ml_models/conformal/__init__.py`
- `backend/app/features/ml_models/conformal/calibrator.py`
- `backend/app/features/ml_models/conformal/coverage_tracker.py`
- `backend/app/features/ml_models/conformal/tests/test_calibrator.py`

### Acceptance Criteria
- [ ] Realized coverage ≈ nominal on held-out data (90% ±3%)
- [ ] Calibrator fits ONLY on calibration slice (assertion in code)
- [ ] Intervals widen in high-local-volatility regions
- [ ] Residual predictor dimensions pinned to [31→16→8→1]

---

## P4.T7: Ensemble Blender (Block A6.1)

**Effort**: M / 1 day
**Dependencies**: P4.T4, P4.T5
**Risk Level**: Medium

### T7.S1: RegimeBlender Implementation [~4 hrs]

Create `backend/app/features/ml_models/ensemble/blender.py`:
```python
class RegimeBlender:
    def __init__(self, base_lstm_w: float = 0.60):  # [NEW - Gap 6: pinned default]
        self.base_lstm_w = base_lstm_w
    
    def blend_horizon(self, lstm_pred, tft_q10, tft_q50, tft_q90) -> float:
        tft_spread = tft_q90 - tft_q10
        spread_z = self._normalize_spread(tft_spread)
        lstm_w = np.clip(self.base_lstm_w + 0.10 * spread_z, 0.40, 0.80)
        return lstm_pred * lstm_w + tft_q50 * (1 - lstm_w)
    
    def _normalize_spread(self, spread) -> float:
        # rolling z-score of recent spreads
        ...
```

Per design formula exactly. Symmetric across 4 horizons. `base_lstm_w=0.60` as pinned default.

### T7.S2: Blender Behavior Tests [~3 hrs]

Create `backend/app/features/ml_models/ensemble/tests/test_blender.py`:
- Test 1: High TFT spread → weight shifts toward LSTM (up to 0.80)
- Test 2: Low TFT spread → weight shifts toward TFT (down to 0.40)
- Test 3: Weights always clipped to [0.40, 0.80]
- Test 4: At average spread, blend is ≈60/40
- Test 5: All 4 horizons use identical rule

### Files to Create
- `backend/app/features/ml_models/ensemble/__init__.py`
- `backend/app/features/ml_models/ensemble/blender.py`
- `backend/app/features/ml_models/ensemble/tests/test_blender.py`

### Acceptance Criteria
- [ ] Weight responds monotonically to TFT spread within clips
- [ ] Average-spread case ≈ 60/40
- [ ] Horizon symmetry verified
- [ ] `base_lstm_w=0.60` pinned as default

---

## P4.T8: Ensemble Orchestrator + Conviction Scoring (Block A6.3)

**Effort**: M / 1 day
**Dependencies**: P4.T7, P4.T6
**Risk Level**: Low

### T8.S1: Conviction Scoring (Derivation A) [~3 hrs]

Create `backend/app/features/ml_models/ensemble/scoring.py`:
```python
def compute_conviction(y_pred: np.ndarray, tft_q10: np.ndarray, tft_q90: np.ndarray) -> np.ndarray:
    sigma = (tft_q90 - tft_q10) / 2.563  # 10-90 spread to ~1σ
    z = y_pred / (sigma + 1e-9)
    return np.clip(z * 25 + 50, 0, 100)
```

Per design §6 formula exactly. Vectorized per ticker per horizon.

### T8.S2: EnsembleOrchestrator [~4 hrs]

Create `backend/app/features/ml_models/ensemble/orchestrator.py`:
```python
class EnsembleOrchestrator:
    def predict(self, lstm_outputs, tft_outputs, features, calibrator, blender, scorer) -> dict:
        # Per horizon: blend → conformal interval → conviction
        # Returns: {pred_t1, lo_t1, hi_t1, conviction_t1, ...} × 4 horizons
        # + raw component arrays for debugging
        ...
```

Sequence: blend (T7) → conformal interval (T6) → conviction (T8.S1). Output maps directly to `predictions` schema.

### Files to Create
- `backend/app/features/ml_models/ensemble/scoring.py`
- `backend/app/features/ml_models/ensemble/orchestrator.py`
- `backend/app/features/ml_models/ensemble/tests/test_orchestrator.py`

### Acceptance Criteria
- [ ] Conviction formula matches design §6 exactly (documented examples verify)
- [ ] Orchestrator produces full 4-horizon prediction package
- [ ] Raw component outputs included for debugging
- [ ] Output maps directly to `predictions` schema

---

## P4.T9: Training Pipeline + Champion/Challenger

**Effort**: L / 2 days
**Dependencies**: P4.T4, P4.T5, P4.T8, P4.T1
**Risk Level**: High

### T9.S1: Portable Training Callable [~1 day]

Create `backend/app/features/ml_models/service.py`:
```python
@dataclass
class TrainingResult:
    training_run: TrainingRun
    artifacts: list[ModelArtifact]
    validation_metrics: dict
    per_epoch_losses: list[float]

async def train_universe(
    universe_id: uuid.UUID,
    as_of_date: date,
    db_session: AsyncSession,
    artifact_store: ArtifactStore,
    hyperparams: dict | None = None,
) -> TrainingResult:
    """Portable, framework-agnostic training callable.
    
    No Prefect/FastAPI imports — callable from local GPU (Prefect) or Colab.
    """
```

Steps:
1. Load feature_matrix for all active tickers in universe
2. Build walk-forward split
3. Create TimeSeriesDataset + DataLoaders
4. Train LSTM (custom loop) on 70% train + 15% validation
5. Train 4 TFTs (Lightning) on respective horizons
6. Fit conformal calibrator on 15% calibration slice
7. Fit residual predictor on calibration slice
8. Evaluate on 15% validation
9. Serialize 7 artifacts, save via artifact_service
10. Record TrainingRun row with window bounds + metrics
11. Return TrainingResult

**Checkpointing** [NEW - Gap 2]: After each model trains successfully, serialize and save its artifact immediately. If a crash occurs mid-training, re-running `train_universe` skips models that already have artifacts for this (universe, training_date, model_role). Implement via:
```python
def _checkpoint_model(universe_id, role, artifact_bytes, training_run_id):
    # Save immediately after training — if crash, resume from checkpoint
    if not artifact_service.exists_for_run(universe_id, role, training_run_id):
        artifact_service.save_artifact(...)
```

### T9.S2: Champion/Challenger Promotion [~4 hrs]

Create `backend/app/features/ml_models/promotion.py`:
- `promote_challenger(challenger_result, universe_id) -> bool`
- Compare challenger vs champion on validation metrics
- Promotion margin configurable (`PROMOTION_MARGIN`, default 0.02 = 2% relative improvement)
- First training auto-promotes (no champion exists)
- All-or-nothing: promote all 7 artifacts atomically or none
- On reject: store challenger artifacts inactive with reason

### T9.S3: Pipeline Tests [~4 hrs]

Create `backend/app/features/ml_models/tests/test_training_pipeline.py`:
- Full small-universe train produces 7 artifacts + TrainingRun row
- Champion/challenger correctly promotes better, rejects worse
- Run status transitions (running→succeeded/failed) persist
- Crash-resume: re-running after simulated partial crash produces complete result

### Files to Create
- `backend/app/features/ml_models/service.py`
- `backend/app/features/ml_models/promotion.py`
- `backend/app/features/ml_models/tests/test_training_pipeline.py`

### Acceptance Criteria
- [ ] `train_universe` runs end-to-end producing 7 artifacts + metrics
- [ ] No Prefect/FastAPI imports (portable)
- [ ] Per-model checkpointing with crash-resume
- [ ] Worse challenger does NOT replace champion
- [ ] First training auto-promotes; decisions recorded on training_runs

---

## P4.T10: Inference Pipeline + Predictions

**Effort**: L / 2 days
**Dependencies**: P4.T9
**Risk Level**: Medium

### T10.S1: Inference Pipeline [~1 day]

Create `backend/app/features/ml_models/inference_service.py`:
```python
async def run_inference(
    universe_id: uuid.UUID,
    inference_date: date,
    db_session: AsyncSession,
    artifact_store: ArtifactStore,
) -> InferenceRun:
```

Steps:
1. Load active 7 artifacts for universe
2. Fetch latest 252 trading days of features per active ticker
3. Run LSTM inference → [N,4]
4. Run 4 TFT inferences → q10/q50/q90 per horizon
5. Pass through EnsembleOrchestrator
6. Write per-ticker predictions (point + interval + conviction + raw arrays)
7. Record InferenceRun with artifact_ids used
8. Skip tickers with <252 days history (log, don't crash)

### T10.S2: Inference Tests [~4 hrs]

Test the inference path end-to-end:
- Predictions land with correct shape
- `UNIQUE(ticker, universe, inference_date)` upsert is idempotent
- Short-history tickers skipped
- Artifact IDs recorded match active champion set

### Files to Create
- `backend/app/features/ml_models/inference_service.py`
- `backend/app/features/ml_models/tests/test_inference.py`

---

## P4.T11: Prefect Retrain + Inference Flows

**Effort**: M / 1 day
**Dependencies**: P4.T9, P4.T10, S2
**Risk Level**: Medium

### T11.S1: Weekly Retrain Flow [~4 hrs]

Create `backend/app/orchestration/flows/weekly_retrain.py`:
```python
@flow(name="weekly_retrain")
async def weekly_retrain():
    for universe in await get_active_universes():
        result = await train_universe_submit(universe.id, date.today())
        if result.status == "succeeded":
            await promote_if_better(result, universe.id)
```
- Schedule: Sundays ~6am ET
- Per-universe isolation (one failure doesn't abort others)
- On-failure hook writes system_alerts row
- Generous timeout for long training runs

### T11.S2: Daily Inference Flow [~3 hrs]

Create `backend/app/orchestration/flows/daily_inference.py`:
```python
@flow(name="daily_inference")
async def daily_inference():
    for universe in await get_active_universes():
        await run_inference_submit(universe.id, today)
```
- Schedule: weekdays ~5:30pm ET (after S2/S3 refresh)
- Per-universe inference with retries
- Depends temporally on data refresh completing

### E2E Flow Integration Test [NEW - Gap 4]

Create `backend/app/features/ml_models/tests/test_prefect_integration.py`:
- Deploy flow to test Prefect instance
- Trigger flow run
- Verify artifacts + predictions landed in DB
- Verify champion/challenger gate worked

### Files to Create
- `backend/app/orchestration/flows/weekly_retrain.py`
- `backend/app/orchestration/flows/daily_inference.py`
- Update `backend/app/orchestration/deployments.py` to register new flows
- `backend/app/features/ml_models/tests/test_prefect_integration.py`

### Acceptance Criteria
- [ ] Weekly retrain deployed + scheduled (Sundays ET)
- [ ] Daily inference deployed + scheduled (weekdays after refresh)
- [ ] Per-universe isolation maintained
- [ ] E2E flow test passes

---

## P4.T12: Model Health UI + API + E2E

**Effort**: L / 2 days
**Dependencies**: P4.T9, P4.T10, P4.T11
**Risk Level**: Low

### T12.S1: Model Health API Endpoints [~4 hrs]

Create `backend/app/features/ml_models/endpoints/`:
- `GET /api/v1/model-health/{universe_id}` — model card (latest run, metrics, coverage)
- `GET /api/v1/model-health/{universe_id}/training-history` — chronological runs
- `GET /api/v1/model-health/{universe_id}/artifacts` — artifact list with active flags
- `POST /api/v1/model-health/{universe_id}/artifacts/{id}/rollback` — re-activate older set
- `POST /api/v1/model-health/{universe_id}/retrain` — trigger Prefect retrain
- `POST /api/v1/model-health/{universe_id}/infer` — trigger Prefect inference
- All admin-only

Create `backend/app/features/ml_models/router.py` — FastAPI router
Register in `backend/app/app.py` via `app.include_router(ml_models_router)`

### T12.S2: Frontend Model Health Dashboard [~1 day]

Create `frontend/src/features/model_health/`:

**Routes** [NEW - Gap 3]:
- `/model-health` — index page (universe selector + summary cards)
- `/model-health/:universeId` — model card (training timeline, val loss curves via Recharts, conformal coverage chart)
- `/model-health/:universeId/training-history` — chronological run list
- `/model-health/:universeId/artifacts` — artifact list + rollback button

**TanStack Query Hooks**:
- `useModelHealth(universeId)` — fetches model card
- `useTrainingHistory(universeId)` — fetches run list
- `useArtifacts(universeId)` — fetches artifact list
- `useRollbackArtifact()` — mutation for rollback action
- `useTriggerRetrain()` — mutation for retrain trigger
- `useTriggerInference()` — mutation for inference trigger

**Polling**: 60s refetch normally, 5s when a run is `running`

**Component Tree**:
```
ModelHealthPage
├── UniverseSelector (dropdown)
├── ModelCard
│   ├── StatusBadge (active champion info)
│   ├── ValLossChart (Recharts line chart)
│   └── CoverageChart (Recharts line chart)
├── TrainingHistoryTable (TanStack Table)
└── ArtifactList
    └── ArtifactRow (with RollbackButton + AlertDialog confirm)
```

**Navigation**: Add link from `UniverseDetailPage` to model-health. Add route to React Router.

### T12.S3: Integration Tests + Features.md [~4 hrs]

Create `backend/app/features/ml_models/tests/test_integration.py`:
- Full ML path: train → promote → infer → predictions → model-health endpoint
- Uses tiny synthetic data (fast, CPU-friendly)

Create `backend/app/features/ml_models/features.md`:
- Document Blocks A4/A5/A6
- Topology diagram
- 3-way split explanation
- Champion/challenger protocol
- Conformal calibration details
- Portable callable + Colab workflow
- Residual predictor architecture (pinned dimensions)

### Files to Create
- `backend/app/features/ml_models/router.py`
- `backend/app/features/ml_models/endpoints/__init__.py`
- `backend/app/features/ml_models/endpoints/model_health.py`
- `backend/app/features/ml_models/dependencies.py`
- `backend/app/features/ml_models/features.md`
- `backend/app/features/ml_models/tests/test_integration.py`
- `frontend/src/features/model_health/pages/ModelHealthPage.tsx`
- `frontend/src/features/model_health/pages/TrainingHistoryPage.tsx`
- `frontend/src/features/model_health/pages/ArtifactListPage.tsx`
- `frontend/src/features/model_health/api/useModelHealth.ts`
- `frontend/src/features/model_health/api/useTrainingHistory.ts`
- `frontend/src/features/model_health/api/useArtifacts.ts`
- `frontend/src/features/model_health/api/useRollbackArtifact.ts`
- `frontend/src/features/model_health/api/useTriggerRetrain.ts`
- `frontend/src/features/model_health/api/useTriggerInference.ts`
- `frontend/src/features/model_health/feature.md`

### Acceptance Criteria
- [ ] Model card, training history, artifact list endpoints return correct data
- [ ] Rollback re-activates older artifact set atomically
- [ ] Retrain/infer triggers kick Prefect runs; admin-only
- [ ] Frontend renders training timeline + val-loss curves + coverage
- [ ] Artifact list shows champion/archived with working rollback
- [ ] In-progress runs poll faster; links from universe detail
- [ ] Integration test covers full path; features.md documented
- [ ] All S4 tests green in CI

---

## Risk Register (Annotated for Gaps)

| ID | Risk | Mitigation | Gap |
|---|---|---|---|
| R1 | Weekly 15-model training too slow | Portable callable + Colab; per-model checkpointing (T9.S1) | G2 |
| R2 | Bad model silently goes live | Champion/challenger + coverage gate | — |
| R3 | Conformal miscalibrated | Calibration-set isolation assertion + coverage test | — |
| R4 | pytorch-forecasting API friction | Dedicated adapter task (T5.S1) | — |
| R5 | MPS/TFT incompatibility | CPU fallback + Colab docs | — |
| R6 | Half-promoted artifacts | All-or-nothing atomic activation (T9.S2) | — |
| R7 | Mismatched normalization | feature_matrix stores pre-normalized data | — |
| R8 | Version drift | Pin pytorch-lightning + pytorch-forecasting together | — |
| R9 | **Residual predictor under/overfits** [NEW] | Pinned architecture [31→16→8→1]; coverage test guards | G5 |
| R10 | **Frontend routing collisions** [NEW] | Pre-defined route map in T12.S2; integration test covers | G3 |
| R11 | **Crash mid-training loses all progress** [NEW] | Per-model checkpointing with resume (T9.S1) | G2 |
| R12 | **Prefect flow not deploying** [NEW] | E2E flow integration test (T11) | G4 |

---

## Assumptions

- Training is a **portable callable** (locked): local-GPU default; Colab escape hatch
- Training loops: **custom PyTorch for LSTM, PyTorch Lightning for TFT** (locked)
- Promotion is **champion/challenger** (locked)
- Conformal calibrates on **calibration slice only** (α=0.10 default)
- LSTM has **no Sigmoid**, uses **HuberLoss**
- Ensemble: **uncertainty-aware** `base_lstm_w=0.60` [PINNED]
- 7 artifacts per universe; old artifacts kept 6 months
- **Residual predictor architecture**: `Linear(31,16) → ReLU → Dropout(0.1) → Linear(16,8) → ReLU → Dropout(0.1) → Linear(8,1) → Softplus` [PINNED]
- **Frontend routes**: `/model-health`, `/model-health/:universeId`, `/model-health/:universeId/training-history`, `/model-health/:universeId/artifacts`
- `promotion_margin=0.02` (2% relative improvement required to replace champion)

---

## End of Stage S4 Plan

**Total tasks**: 13 (P4.T0 – P4.T12)
**Total estimated effort**: 22–30 dev days (1 dev), 14–19 days (ML + backend pair)
