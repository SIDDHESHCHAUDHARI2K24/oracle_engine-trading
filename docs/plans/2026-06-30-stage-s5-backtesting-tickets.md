# Stage S5 — Backtesting + Conviction Tickets — Implementation Plan

> **Date**: 2026-06-30
> **Status**: Ready for execution
> **Source**: `features-to-develop/development-plan-S5.md`, `docs/mbi-pipeline-a-v1-design.md` §7–§8
> **Previous**: S4 — ML Models (complete, 56 tests + 1 E2E passing)
> **Next**: S6 — Monitoring & Polish

---

## 0. Pre-Flight: Codebase Context & Path Corrections

### Correct File Paths

AGENTS.md references `backend/src/backend/features/` but actual code lives in `backend/app/features/`. All S5 work uses:

```
backend/app/features/backtesting/          ← NEW (create all backtest code here)
backend/app/features/conviction_tickets/   ← NEW (create all ticket code here)
backend/app/orchestration/flows/           ← ADD: weekly_backtest.py, outcome_resolution.py
backend/app/orchestration/flows/daily_inference.py  ← MODIFY: add filter + emission tasks
backend/alembic/versions/                  ← New migration for S5 tables
frontend/src/features/backtesting/        ← NEW (backtest explorer UI)
frontend/src/features/conviction_tickets/ ← NEW (inbox, detail, history UI)
```

### Builds On

| Dependency | Path | Key Interface |
|---|---|---|
| S4 predictions | `app/features/ml_models/models.py` | `Prediction` ORM — 20 fields: pred/lo/hi/conviction per horizon + lstm_outputs, tft_q10/q50/q90 |
| S4 inference run | `app/features/ml_models/models.py` | `InferenceRun` ORM — per-universe per-day, `inference_date`, `artifact_ids` JSONB, `num_tickers_scored` |
| S4 conformal calibrator | `app/features/ml_models/conformal/calibrator.py` | `ConformalCalibrator` — `quantiles: dict[int, float]`, `residual_predictor`, `alpha=0.10` |
| S3 feature_matrix | `app/features/feature_engineering/models.py` | `FeatureMatrix` ORM — 31 features + 4 targets per (ticker, bar_date), including bb_lower, sma_50/200, atr_14 |
| S2 ohlcv_bars | `app/features/data_ingestion/models.py` | `OHLCVBar` ORM — close prices, SPY bars |
| S2 trading calendar | `app/features/data_ingestion/shared/trading_calendar.py` | `trading_days()`, `last_n_trading_days()`, `is_trading_day()` |
| S1 active membership | `app/features/universes/repository.py` | `list_active_tickers_for_universe()` |
| S0 artifact store | `app/core/services/artifact_store.py` | `ArtifactStore` Protocol — put/get/exists/delete/list |
| S0 DB fixtures | `app/features/conftest.py` | `database_url` + `db_session` (testcontainers Postgres+TimescaleDB) |
| S2 Prefect infra | `app/orchestration/` | `deployments.py`, existing flows |

### Dependencies Available

```toml
# Already in pyproject.toml
"pandas>=1.5.0",
"numpy>=1.24.0",
"scipy>=1.11.0",             # for StatArb linregress
"torch>=2.2.0",              # for conformal loading
"tenacity>=9.1.4",           # retry logic
"sqlalchemy[asyncio]>=2.0",  # ORM
# NEED TO ADD:
"vectorbt>=0.6.0,<1.0",     # Backtest engine — NOTE: requires Python 3.11 (not 3.12)
```

**Python version note**: `vectorbt` does not support Python 3.12+. The backend uses Python 3.12+ per AGENTS.md. We may need to run vectorbt in a subprocess with Python 3.11 or use an alternative. Document this constraint.

### Test Patterns to Follow

- Async DB tests: `@pytest.mark.asyncio` + `db_session` fixture (transactions roll back)
- Pure math/strategy tests: synchronous + synthetic data + no DB
- HTTP integration: `httpx.AsyncClient(transport=ASGITransport(app=app))` + `dependency_overrides`
- Mocking: `pytest.monkeypatch.setattr("full.dotted.path", lambda: ...)`, NOT `unittest.mock`
- DB container: session-scoped `testcontainers.postgres.PostgresContainer` (TimescaleDB image)
- TDD mandatory: RED (write test, see it fail) → GREEN (implement) → REFACTOR

---

## Critical Gap: W_max Not Stored (P5.T0)

### Problem

The S5 filter gate requires `W_max` — the per-universe 90th percentile conformal interval width from the calibration set. This was supposed to be computed at S4 train time and stored on the conformal artifact's metadata, but **S4 never implemented W_max computation**. The conformal artifact currently stores:
- `alpha` (float)
- `quantiles` (dict[int, float] — per-horizon conformal quantiles)
- `residual_predictor_state` (MLP state dict)

No width statistics are saved.

### Resolution: P5.T0 — Retroactive W_max Backfill

Add `compute_W_max()` to `ConformalCalibrator` that takes calibration split features and returns per-horizon 90th-percentile widths. Patch S4's `train_universe()` to call it and store W_max on the conformal artifact's `model_metadata`. Run a one-time retroactive computation for any existing trained models (if any exist in DB).

### What P5.T0 Touches

| Action | File |
|---|---|
| Add `compute_W_max()` method | `backend/app/features/ml_models/conformal/calibrator.py` |
| Store W_max in metadata at train time | `backend/app/features/ml_models/service.py` (train_universe) |
| Load W_max from metadata at inference/filter time | `backend/app/features/ml_models/inference_service.py` |
| Add W_max accessor to calibration data | `backend/app/features/ml_models/conformal/calibrator.py` |
| Unit test W_max computation | `backend/app/features/ml_models/conformal/tests/test_calibrator.py` |
| Migration: add `w_max` JSONB column to training_runs | `backend/alembic/versions/` |

---

## Dependency Map (Updated with P5.T0)

```
S4 (predictions + conformal) ──> P5.T0 (W_max backfill) ──> P5.T6 (Filter gate)
       │                                                   
       ├─────────────────────────────────────────────────> P5.T1 (Schema) ──> P5.T2 ──> P5.T3 ──> P5.T4 ──> P5.T5
       │                                                                                          │
       │                                                                                          ▼
       └─────────────────────────────────────────────────────────────────────────────────────> P5.T6
                                                                                                    │
                                                                                                    ▼
                                                                                              P5.T7 (Ticket emission)
                                                                                               │         │
                                                                                               ▼         ▼
                                                                                         P5.T8       P5.T9 (UI)
                                                                                          │            │
                                                                                          └─────┬──────┘
                                                                                                ▼
                                                                                          P5.T10 (Integration)
```

**Critical path**: `S4 → P5.T0 → P5.T1 → P5.T2 → P5.T3 → P5.T4 → P5.T6 → P5.T7 → P5.T8 → P5.T10`

**Parallelizable**:
- P5.T0 and P5.T1 can start together (both depend on S4 only)
- P5.T2 (strategies) and the UI prep work (types, routes) can be parallel
- P5.T9 (frontend) can start once P5.T4 (backtest endpoints) and P5.T7 (ticket endpoints) exist
- P5.T5 (weekly flow) and P5.T6 (filter gate) can run in parallel after P5.T4

### Parallel Work Streams

| Stream | Tasks | Can run concurrently with |
|---|---|---|
| W_max fix | T0 | T1 (both pure S4 dependencies) |
| Backend DB layer | T1 → T2 → T3 → T4 | Nothing else until T4 done |
| Strategy logic | T2 (sub-tasks S2, S3) | Once S1 passes; parallel with T3 |
| Orchestration | T5 (weekly flow) | T6, T7 (different concerns) |
| Filter + Tickets | T6 → T7 → T8 | T5, T9 (converge at T10) |
| Frontend | T9 | Starts after T4+T7 endpoints exist |

---

## Task P5.T0: W_max Backfill (Pre-requisite Gap Fix)

**Feature**: Cross-feature — S4 ConformalCalibrator enhancement
**Effort**: S / half day
**Dependencies**: S4 (conformal calibrator artifact)
**Risk Level**: Low

### Sub-task P5.T0.S1: Add `compute_W_max()` to ConformalCalibrator

**Description**: Add a method `compute_calibration_widths(features, predictions, targets)` that:
1. Runs the residual predictor on calibration features → `r_hat`
2. Computes predicted interval width per sample = `2 * q_h * r_hat`
3. Returns per-horizon 90th percentile width as `{horizon_index: float}`

**Files**:
- `backend/app/features/ml_models/conformal/calibrator.py` — add method
- `backend/app/features/ml_models/conformal/tests/test_calibrator.py` — add 2 tests

**Implementation Hints**:
```python
def compute_W_max(self, features: np.ndarray) -> dict[int, float]:
    """Compute 90th percentile conformal interval widths per horizon from calibration features."""
    r_hat = self._predict_residuals(features)  # shape [n, 4]
    widths = {}
    for h, q_h in self.quantiles.items():
        w_h = 2.0 * q_h * r_hat[:, h]
        widths[h] = float(np.percentile(w_h, 90))
    return widths
```
Use `_predict_residuals()` already implemented in `predict()` path. Assert widths are positive and ordered (higher horizon → wider).

**Test Plan** (TDD — write first):
- `test_W_max_positive_and_ordered`: Supply known feature variation → assert widths > 0 and T1 < T5 < T10 < T15
- `test_W_max_constant_features`: Supply constant features → assert widths are finite and equal across samples

**Dependencies**: P4.T6 (conformal calibrator)
**Effort**: S / 2 hrs
**Acceptance Criteria**:
- `compute_W_max()` returns dict with 4 positive, monotonically-increasing floats
- Widths derived from `quantiles` and `residual_predictor` correctly
- Tests FAIL initially (RED), then pass (GREEN)

### Sub-task P5.T0.S2: Store W_max during train_universe()

**Description**: After fitting the conformal calibrator in `train_universe()`, call `compute_W_max()` on the calibration split features and store the result in the conformal artifact's `model_metadata` as `{"w_max": {"t1": 0.023, "t5": 0.041, ...}}`.

**Files**:
- `backend/app/features/ml_models/service.py` — add W_max computation after calibrator fit (~line 395-435)
- `backend/app/features/ml_models/inference_service.py` — add `_load_w_max()` helper to extract W_max from loaded conformal artifact metadata

**Implementation Hints**: After `calibrator.fit(...)` succeeds, get the calibration-split feature matrix `X_cal`, call `calibrator.compute_W_max(X_cal)`, and embed in the artifact metadata dict before saving. The inference path needs a helper `_load_w_max(conformal_artifact: ModelArtifact) -> dict[int, float]` that reads `artifact.model_metadata.get("w_max", {})`.

**Test Plan**: Extend existing training pipeline test in `tests/test_training_pipeline.py` to assert W_max is stored in the conformal artifact's metadata after training.

**Dependencies**: P5.T0.S1
**Effort**: S / 2 hrs
**Acceptance Criteria**:
- `train_universe()` saves W_max in conformal artifact `model_metadata`
- `_load_w_max()` extracts it correctly
- Training pipeline test extended to assert W_max present
- Fallback to `{}` if metadata missing (backward-compat)

---

## Task P5.T1: Backtest + Ticket Schema

**Feature**: Features 6 + 7 — persistence
**Effort**: M / 1 day
**Dependencies**: P5.T0 (for W_max access pattern), S4
**Risk Level**: Low

### Sub-task P5.T1.S1: Define ORM Models

**Description**: Create SQLAlchemy 2.0 async ORM models for all four new tables per design §7–§8.

**Files to create**:
- `backend/app/features/backtesting/__init__.py`
- `backend/app/features/backtesting/models.py` — `BacktestRun`, `BacktestMetrics`
- `backend/app/features/conviction_tickets/__init__.py`
- `backend/app/features/conviction_tickets/models.py` — `ConvictionTicket`, `FilterRun`

**Models detail**:

```python
# backtesting/models.py

class BacktestRun(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "backtest_runs"
    universe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universes.id"), nullable=False)
    triggered_by: Mapped[str]  # 'weekly_scheduled' | 'on_demand'
    backtest_period_start: Mapped[date]
    backtest_period_end: Mapped[date]
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None]
    status: Mapped[str]  # 'running' | 'succeeded' | 'failed'
    num_tickers: Mapped[int | None]
    num_strategies: Mapped[int] = mapped_column(default=4)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

class BacktestMetrics(Base, UUIDPrimaryKey):
    __tablename__ = "backtest_metrics"
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("backtest_runs.id"), nullable=False)
    ticker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    strategy_name: Mapped[str]  # 'mean_reversion' | 'momentum_cross' | 'volatility_breakout' | 'stat_arb'
    sharpe_ratio: Mapped[float | None]
    max_drawdown: Mapped[float | None]
    total_return: Mapped[float | None]
    win_rate: Mapped[float | None]
    profit_factor: Mapped[float | None]
    total_trades: Mapped[int | None]
    passed: Mapped[bool]  # GENERATED ALWAYS AS (...)
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # equity_curve stored as JSONB array of {date, value} for frontend charts
    equity_curve: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    __table_args__ = (
        UniqueConstraint("backtest_run_id", "ticker_id", "strategy_name"),
        Index("idx_metrics_ticker_strategy_time", "ticker_id", "strategy_name", "computed_at"),
        Index("idx_metrics_run_passed", "backtest_run_id", "passed"),
    )
```

```python
# conviction_tickets/models.py

class ConvictionTicket(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "conviction_tickets"
    inference_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inference_runs.id"), nullable=False)
    ticker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    universe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universes.id"), nullable=False)
    inference_date: Mapped[date]
    horizon: Mapped[str]  # 'T1' | 'T5' | 'T10' | 'T15'
    direction: Mapped[str] = mapped_column(default="LONG")
    predicted_return: Mapped[float]
    conviction_score: Mapped[float]
    conformal_lower: Mapped[float]
    conformal_upper: Mapped[float]
    conformal_alpha: Mapped[float] = mapped_column(default=0.10)
    backtest_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("backtest_runs.id"), nullable=True)
    backtest_passes: Mapped[int]
    backtest_pass_strategies: Mapped[list] = mapped_column(ARRAY(String), default=list)
    status: Mapped[str] = mapped_column(default="TRADABLE")  # TRADABLE|REVIEWED|ACTIONED|RESOLVED|EXPIRED
    resolution_date: Mapped[date]
    actual_return: Mapped[float | None]
    outcome: Mapped[str | None]  # 'win' | 'loss' | 'flat'
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_notes: Mapped[str | None]
    updated_at: Mapped[datetime | None]
    __table_args__ = (
        UniqueConstraint("inference_run_id", "ticker_id", "horizon"),
        Index("idx_tickets_inbox", "universe_id", "status", "conviction_score"),
        Index("idx_tickets_resolution", "resolution_date", "status"),
        Index("idx_tickets_ticker_date", "ticker_id", "inference_date"),
    )

class FilterRun(Base, UUIDPrimaryKey):
    __tablename__ = "filter_runs"
    inference_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inference_runs.id"), nullable=False)
    backtest_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("backtest_runs.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None]
    num_predictions_evaluated: Mapped[int | None]
    num_tickets_emitted: Mapped[int | None]
    filter_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
```

**Implementation Hints**: The `passed` column on `BacktestMetrics` must be a **server-side GENERATED ALWAYS AS** column. In SQLAlchemy 2.0, use `Computed()`:
```python
from sqlalchemy import Computed
passed: Mapped[bool] = mapped_column(
    Boolean,
    Computed("sharpe_ratio > 1.5 AND total_trades >= 10 AND max_drawdown > -0.40", persisted=True),
    nullable=False,
)
```
Register both model modules in `alembic/env.py` for autogenerate support.

**Test Plan** (TDD): Write a test that creates model instances and verifies `passed` auto-computes when metrics are inserted via raw SQL. Test enum constraints. These are schema-verification tests.

**Dependencies**: S4
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- Models match design §7–§8 column-for-column
- `passed` generated column encodes the locked filter criteria
- Status + outcome enums present; models registered in alembic env

### Sub-task P5.T1.S2: Author the Migration

**Description**: Write the Alembic migration creating all four tables with specified indexes.

**File to create**: `backend/alembic/versions/c1d2e3f4a5b6_add_backtesting_conviction_tickets_tables.py`

**Implementation Hints**:
- Down revision: `b1c2d3e4f5a6` (latest S4 migration)
- Create `backtest_runs`, `backtest_metrics` (with generated column), `conviction_tickets`, `filter_runs`
- All indexes per design spec
- conviction_tickets is NOT a hypertable (standard Postgres table — lower volume than predictions)
- Include `CREATE TYPE` for enums if using PostgreSQL native enums, or use VARCHAR with CHECK constraints
- IMPORTANT: SQLAlchemy's `Computed()` for `passed` column — verify it renders correctly in Alembic. May need a raw SQL `ALTER TABLE` if autogenerate doesn't handle it.

**PostgreSQL-specific**:
```sql
ALTER TABLE backtest_metrics ADD COLUMN passed BOOLEAN
  GENERATED ALWAYS AS (sharpe_ratio > 1.5 AND total_trades >= 10 AND max_drawdown > -0.40) STORED;
```

If any of the columns are NULL (e.g., no-trades case), the generated expression should evaluate to FALSE (COALESCE or use NULL-safe comparison).

**Test Plan**: Run `alembic upgrade head` and `alembic downgrade -1` in a test DB. Insert a backtest_metrics row with passing values, verify `passed` is TRUE. Insert a row with failing values, verify FALSE.

**Dependencies**: P5.T1.S1
**Effort**: S / 3 hrs
**Acceptance Criteria**:
- Migration creates all four tables with specified indexes
- `passed` generated column works (insert metrics, verify computed value)
- `upgrade`/`downgrade` round-trip clean

---

## Task P5.T2: The 4 Strategies (Block A7.1)

**Feature**: Feature 6 (Backtesting) — strategies
**Effort**: L / 2 days
**Dependencies**: P5.T1 (schema), S3 (feature_matrix — technical features)
**Risk Level**: Medium

### Locked Decisions
- Strategies read **pre-computed technical features from S3's feature_matrix** (already lookahead-audited), not recomputed
- Crossover logic uses `.shift(1)` previous-bar comparison
- Signals use only completed-bar data (no same-bar future leakage)

### Sub-task P5.T2.S1: BaseStrategy ABC + Strategy Tests (TDD — write first)

**Description**: Define abstract base class and write RED tests for all 4 strategies.

**Files to create**:
- `backend/app/features/backtesting/shared/__init__.py`
- `backend/app/features/backtesting/shared/base.py` — `BaseStrategy(ABC)`
- `backend/app/features/backtesting/strategies/__init__.py`
- `backend/app/features/backtesting/strategies/tests/__init__.py`
- `backend/app/features/backtesting/strategies/tests/test_mean_reversion.py`
- `backend/app/features/backtesting/strategies/tests/test_momentum_cross.py`
- `backend/app/features/backtesting/strategies/tests/test_volatility_breakout.py`
- `backend/app/features/backtesting/strategies/tests/test_stat_arb.py`

**BaseStrategy contract**:
```python
class BaseStrategy(ABC):
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Return (entries: pd.Series[bool], exits: pd.Series[bool])"""
        ...
```

**Test fixture design**: For each strategy, build small (20-30 row) DataFrames with:
- Required feature columns (close, bb_lower, bb_middle, sma_50, sma_200, atr_14, etc.)
- Prices constructed so entry/exit conditions are clearly met or not met at specific bars

**Lookahead safety test**: Assert that a signal at bar `t` uses only data from rows ≤ `t` (i.e., no future bars accessed). This can be tested by constructing a fixture and verifying that changing future rows doesn't change past signals.

**Dependencies**: P5.T1.S1, S3, P0.T3.S3
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- `BaseStrategy` ABC defined with exact signal-tuple contract
- Tests FAIL initially (RED) for all 4 strategies
- Each strategy's entry/exit + lookahead-safety covered
- At least 3 test cases per strategy: clear entry, clear exit, no-signal edge case

### Sub-task P5.T2.S2: Implement MeanReversion + MomentumCross

**Description**: Implement MeanReversion (entry: `close < bb_lower`, exit: `close > bb_middle`) and MomentumCross (entry: `sma_50 crosses above sma_200`, exit: inverse crossover).

**Files to create**:
- `backend/app/features/backtesting/strategies/mean_reversion.py`
- `backend/app/features/backtesting/strategies/momentum_cross.py`

**Implementation Hints**:
```python
# MeanReversion
entries = df['close'] < df['bb_lower']
exits = df['close'] > df['bb_middle']

# MomentumCross — previous-bar crossover
entries = (df['sma_50'] > df['sma_200']) & (df['sma_50'].shift(1) <= df['sma_200'].shift(1))
exits = (df['sma_50'] < df['sma_200']) & (df['sma_50'].shift(1) >= df['sma_200'].shift(1))
```
Features come from `feature_matrix` columns: `bb_lower`, `bb_middle`, `sma_50`, `sma_200`, `close`. The orchestrator (T4) will load the feature_matrix and pass it as a DataFrame — strategies only consume `df` columns, they don't know the source.

**Dependencies**: P5.T2.S1
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- Both strategies pass their P5.T2.S1 tests (GREEN)
- Crossover logic uses `.shift(1)` previous-bar comparison
- No lookahead: changing future bars doesn't change past signals

### Sub-task P5.T2.S3: Implement VolatilityBreakout + StatArb

**Description**: Implement VolatilityBreakout and StatArb strategies.

**Files to create**:
- `backend/app/features/backtesting/strategies/volatility_breakout.py`
- `backend/app/features/backtesting/strategies/stat_arb.py`

**Implementation Hints**:

VolatilityBreakout:
```python
atr_ma14 = df['atr_14'].rolling(14).mean()
rolling_high20 = df['close'].rolling(20).max().shift(1)  # shift: previous bar's 20-day high
entries = (df['atr_14'] > 1.25 * atr_ma14) & (df['close'] > rolling_high20)
exits = df['close'] < 0.95 * df['close'].rolling(20).max()
```

StatArb:
```python
from scipy.stats import linregress
# Requires SPY close aligned to asset dates — orchestrator provides this as df['spy_close']
residuals = []
for i in range(60, len(df)):
    asset_slice = df['close'].iloc[i-60:i]
    spy_slice = df['spy_close'].iloc[i-60:i]
    result = linregress(spy_slice, asset_slice)
    predicted = result.slope * df['spy_close'].iloc[i] + result.intercept
    residuals.append(df['close'].iloc[i] - predicted)
residual_series = pd.Series([np.nan]*60 + residuals, index=df.index)
z_score = (residual_series - residual_series.rolling(60).mean()) / residual_series.rolling(60).std()
entries = z_score < -2.0
exits = z_score > -0.5
```

**Edge cases**: Missing SPY data (shorter history) → skip ticker gracefully. NaN in rolling windows → treat as no signal.

**Dependencies**: P5.T2.S1
**Effort**: M / 4 hrs
**Risk Flags**: StatArb is complex — test with a known cointegrated fixture (construct synthetic SPY + asset prices with a known relationship).
**Acceptance Criteria**:
- Both strategies pass their P5.T2.S1 tests (GREEN)
- StatArb aligns asset/SPY dates correctly; rolling OLS residual computed
- Edge cases (short SPY history) handled gracefully — no crash, returns empty signals
- NaN handling: NaN entries/exits treated as False (no signal)

---

## Task P5.T3: VectorBT Metrics Engine (Block A7.2)

**Feature**: Feature 6 — backtest execution
**Effort**: M / 1 day
**Dependencies**: P5.T2 (strategies implemented)
**Risk Level**: Medium

### Python Version Constraint

`vectorbt` requires Python 3.11 or lower. If the project runs Python 3.12+, options:
1. **Subprocess**: Run vectorbt in a Python 3.11 subprocess, passing data via pickle/temp files
2. **Alternative**: Port the portfolio metrics computation to pure numpy/pandas if feasible
3. **Conda env**: Switch project to Python 3.11

Document the chosen approach and its rationale.

### Sub-task P5.T3.S1: Implement the MetricsEngine

**Description**: Run a strategy's signals through vectorbt Portfolio and extract 6 metrics.

**File to create**: `backend/app/features/backtesting/shared/metrics_engine.py`

**Implementation**:
```python
import vectorbt as vbt

class MetricsEngine:
    def __init__(self, init_cash: float = 100_000.0, fees: float = 0.001,
                 risk_free: float = 0.045, freq: str = "1D"):
        self.init_cash = init_cash
        self.fees = fees
        self.risk_free = risk_free
        self.freq = freq

    def run(self, close: pd.Series, entries: pd.Series, exits: pd.Series) -> dict:
        """Run backtest and return 6-metric dict."""
        if not entries.any():
            return self._empty_metrics()

        portfolio = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            init_cash=self.init_cash,
            fees=self.fees,
            freq=self.freq,
        )

        trades = portfolio.trades
        if trades.count() == 0:
            return self._empty_metrics()

        gross_profits = trades.records[trades.records['pnl'] > 0]['pnl'].sum() if len(trades.records) > 0 else 0.0
        gross_losses = abs(trades.records[trades.records['pnl'] < 0]['pnl'].sum()) if len(trades.records) > 0 else 0.0
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else (float('inf') if gross_profits > 0 else 0.0)

        return {
            "sharpe_ratio": float(portfolio.sharpe_ratio(risk_free=self.risk_free)),
            "max_drawdown": float(portfolio.max_drawdown()),
            "total_return": float(portfolio.total_return()),
            "win_rate": float(trades.win_rate() or 0.0),
            "profit_factor": float(profit_factor),
            "total_trades": int(trades.count()),
            "equity_curve": self._extract_equity_curve(portfolio),
        }

    def _empty_metrics(self) -> dict:
        return {
            "sharpe_ratio": 0.0, "max_drawdown": 0.0, "total_return": 0.0,
            "win_rate": 0.0, "profit_factor": 0.0, "total_trades": 0,
            "equity_curve": [],
        }

    def _extract_equity_curve(self, portfolio) -> list[dict]:
        """Return equity curve as [{date, value}, ...] for frontend charts."""
        values = portfolio.value()
        return [{"date": str(idx.date()), "value": float(v)} for idx, v in values.items()]
```

**No-trades handling**: Return zero/NaN metrics and `passed` will be False (generated column). Don't crash.

**Dependencies**: P5.T2.S2, P5.T2.S3
**Effort**: M / 4 hrs
**Risk Flags**: profit_factor with zero losses → handle div-by-zero → return inf or 0.0.
**Acceptance Criteria**:
- Extracts exactly 6 metrics + equity curve with spec's global params
- No-trades and zero-loss edge cases handled (no crash)
- Sharpe uses risk-free 4.5%
- equity_curve serialized as list of {date, value} dicts

### Sub-task P5.T3.S2: MetricsEngine Tests

**Description**: Test engine against known-profitable and known-flat signal fixtures.

**File to create**: `backend/app/features/backtesting/shared/tests/__init__.py`
`backend/app/features/backtesting/shared/tests/test_metrics_engine.py`

**Test Plan**:
1. `test_profitable_fixture`: Construct price series with clear uptrend, entry at start, exit at end → assert positive sharpe, positive total_return, total_trades=1, win_rate=1.0
2. `test_flat_fixture`: Construct flat price series → assert minimal trades, passed would be False
3. `test_no_trades_does_not_crash`: Entries all False → returns empty metrics, no crash
4. `test_zero_losses_profit_factor`: All wins → profit_factor is inf or handled
5. `test_equity_curve_format`: Assert equity_curve is list of {date, value} with increasing values on uptrend
6. `test_sharpe_uses_risk_free`: Cross-check one Sharpe against manual computation

**Dependencies**: P5.T3.S1
**Effort**: S / 3 hrs
**Acceptance Criteria**:
- Profitable fixture yields positive metrics; flat fixture yields near-zero metrics
- All 6 metrics asserted present and typed
- One metric cross-checked against manual computation
- No-trades and edge cases don't crash

---

## Task P5.T4: Backtest Orchestrator

**Feature**: Feature 6 — orchestration
**Effort**: L / 2 days
**Dependencies**: P5.T3 (metrics engine), S1 (active membership query)
**Risk Level**: Medium

### Sub-task P5.T4.S1: Implement the BacktestOrchestrator

**Description**: Orchestrate backtest runs across active members × 4 strategies over the 5-year window.

**Files to create**:
- `backend/app/features/backtesting/repository.py` — DB persistence for backtest_runs + backtest_metrics
- `backend/app/features/backtesting/service.py` — `BacktestOrchestrator`

**Repository pattern** (follow S3/S4 patterns — module-level async functions):
```python
async def create_backtest_run(session, universe_id, triggered_by, period_start, period_end) -> BacktestRun
async def complete_backtest_run(session, run_id, status, num_tickers, error=None) -> BacktestRun
async def upsert_backtest_metrics(session, records: list[dict]) -> int
async def get_latest_backtest_run(session, universe_id) -> BacktestRun | None
async def get_metrics_for_ticker(session, ticker_id, run_id=None) -> list[BacktestMetrics]
async def get_latest_metrics_for_ticker(session, ticker_id) -> list[BacktestMetrics]
async def get_pass_summary(session, universe_id, run_id) -> list[dict]  # per-ticker pass counts
```

**Orchestrator**:
```python
class BacktestOrchestrator:
    def __init__(self, metrics_engine: MetricsEngine | None = None):
        self.strategies = {
            "mean_reversion": MeanReversion(),
            "momentum_cross": MomentumCross(),
            "volatility_breakout": VolatilityBreakout(),
            "stat_arb": StatArb(),
        }
        self.metrics = metrics_engine or MetricsEngine()

    async def run_universe(
        self, session, universe_id, period_start, period_end,
        triggered_by="on_demand", n_jobs=-1
    ) -> BacktestRun:
        """Run all 4 strategies on all active members over the window."""
        # 1. Get active ticker IDs
        # 2. Load SPY close once for StatArb
        # 3. Create BacktestRun record
        # 4. For each ticker (parallel via joblib):
        #    a. Load feature_matrix rows for the window
        #    b. Get OHLCV close
        #    c. Run 4 strategies through MetricsEngine
        #    d. Collect metrics
        # 5. Upsert all metrics
        # 6. Complete BacktestRun
        # Per-ticker isolation: one failure doesn't abort the run
```

**Parallelization**: Reuse S3's joblib pattern for per-ticker parallelism. SPY data loaded once and shared across all tickers.

**StatArb SPY handling**: Load SPY close from `ohlcv_bars` for the backtest window once, align to each asset's trading dates. If an asset has dates where SPY has no data, skip those bars.

**Dependencies**: P5.T3.S1, S1 (list_active_tickers_for_universe)
**Effort**: L / 1 day
**Risk Flags**: 5-year window × active members × 4 strategies = significant compute. Document runtime. StatArb rolling OLS is expensive — consider windowing optimization.
**Acceptance Criteria**:
- Backtests all active members × 4 strategies over the 5y window
- Per-ticker isolation; run lifecycle persisted; metrics + `passed` stored
- Parallelized; SPY loaded once for StatArb
- One ticker failure doesn't abort the entire run

### Sub-task P5.T4.S2: Backtest API Endpoints

**Description**: Expose backtest trigger, universe view, and ticker detail endpoints.

**Files to create**:
- `backend/app/features/backtesting/schemas.py` — Pydantic v2 schemas
- `backend/app/features/backtesting/router.py` — `APIRouter(prefix="/api/v1/backtests")`
- `backend/app/features/backtesting/dependencies.py`
- `backend/app/features/backtesting/endpoints/__init__.py`
- `backend/app/features/backtesting/endpoints/backtest.py`

**Endpoints**:
```python
POST /api/v1/backtests/trigger
    # Query: universe_id (required), ticker_id (optional — single-ticker mode)
    # Admin-only
    # Returns: {backtest_run_id, status: "queued"}

GET /api/v1/backtests/{universe_id}
    # Returns: per-ticker pass badges from latest run
    # Response: {universe_id, run: {id, period_start, period_end, status},
    #            tickers: [{ticker_id, symbol, passes: 3, strategies: {mean_reversion: pass, ...}}]}

GET /api/v1/backtests/{universe_id}/{ticker_id}
    # Returns: 4 strategies' 6 metrics + equity curves for charts
    # Response: {ticker: {id, symbol}, strategies: {mean_reversion: {metrics..., equity_curve}, ...}}
```

**Single-ticker trigger**: Calls orchestrator synchronously for one ticker.
**Full-universe trigger**: Dispatches to Prefect `weekly_backtest` deployment for the universe.

**Dependencies**: P5.T4.S1
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- Trigger works for single-ticker (sync) and full-universe (Prefect dispatch)
- Universe view returns per-ticker pass badges; ticker view returns 6 metrics + equity curves
- Admin-only (role check)
- All endpoints return the standard API error envelope

---

## Task P5.T5: Weekly Backtest Flow

**Feature**: Feature 9 (Orchestration) — backtest flow
**Effort**: S / half day
**Dependencies**: P5.T4 (orchestrator), S2 (Prefect)
**Risk Level**: Low

### Sub-task P5.T5.S1: Implement the weekly_backtest flow

**Description**: Prefect flow that runs BacktestOrchestrator for all active universes on Sundays 4am ET (before the 6am retrain).

**File to create**: `backend/app/orchestration/flows/weekly_backtest.py`

**Flow structure** (following existing pattern from `weekly_retrain.py`):
```python
from prefect import flow, task
from app.features.universes.repository import list_universes
from app.features.backtesting.service import BacktestOrchestrator

@task(retries=1, timeout_seconds=7200)
async def backtest_universe(universe_id, period_start, period_end):
    orchestrator = BacktestOrchestrator()
    async with get_session() as session:
        return await orchestrator.run_universe(
            session, universe_id, period_start, period_end,
            triggered_by="weekly_scheduled"
        )

@flow(name="weekly_backtest")
async def weekly_backtest_flow():
    async with get_session() as session:
        universes = await list_universes(session)
    for u in universes:
        await backtest_universe(u.id, ...)
```

**Schedule**: Sunday 4am ET per design §7 — before the 6am retrain so fresh backtest results exist for the week's filtering.

**Dependencies**: P5.T4.S1, P2.T3.S2
**Effort**: S / 3 hrs
**Acceptance Criteria**:
- Weekly backtest deployed + scheduled (Sundays 4am ET) + on-demand triggerable
- Per-universe isolation (one universe failing doesn't block others)
- Results persisted for the week's daily filtering
- Registered in `orchestration/deployments.py`

---

## Task P5.T6: Filter Gate (Block A8)

**Feature**: Feature 7 (Conviction Tickets) — filter
**Effort**: L / 2 days
**Dependencies**: P5.T0 (W_max available), P5.T4 (backtest results), S4 (predictions)
**Risk Level**: Medium

### Locked Decisions
- W_max comes from the conformal artifact's model_metadata per-universe (P5.T0)
- Filter reads freshest persisted backtest_metrics (not waiting on a run)
- Per-horizon independence: a ticker passing only one horizon emits one ticket
- Long-only: predicted_return > 0
- Missing backtest → 0 passes (fails ≥2 criterion), don't crash

### Sub-task P5.T6.S1: Filter Gate Tests (TDD — write first)

**Description**: Write RED tests for the locked 4-criteria filter gate.

**File to create**: `backend/app/features/conviction_tickets/filter/__init__.py`
`backend/app/features/conviction_tickets/filter/tests/__init__.py`
`backend/app/features/conviction_tickets/filter/tests/test_gate.py`

**Test cases** (at least 8):
1. `test_conviction_at_threshold_fails`: conviction=67 → fails; conviction=67.01 → passes on conviction criterion
2. `test_negative_predicted_return_fails`: predicted_return <= 0 → always fails
3. `test_backtest_pass_count_lt_2_fails`: <2 strategies passing → fails
4. `test_conformal_width_exceeds_W_max_fails`: width >= W_max → fails
5. `test_all_criteria_pass`: All 4 pass → ticket emitted
6. `test_per_horizon_independence`: T+5 passes but T+10 fails → one T+5 ticket
7. `test_missing_backtest_zero_passes`: No backtest_metrics for ticker → 0 passes → fails
8. `test_per_universe_W_max`: Different W_max per universe → correct width check

**Test fixture**: Create synthetic Predictions with varying pred/conviction/width values, mock backtest_metrics with controllable pass counts, provide W_max dict.

**Dependencies**: P5.T1.S1, S4, P5.T0
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- Tests FAIL initially (RED)
- Each of the 4 criteria tested at its boundary
- Per-horizon independence asserted
- Missing-backtest case covered

### Sub-task P5.T6.S2: Implement the Filter Gate

**Description**: Implement `apply_filter()` to pass P5.T6.S1 tests.

**File to create**: `backend/app/features/conviction_tickets/filter/gate.py`

**Implementation**:
```python
async def apply_filter(
    session: AsyncSession,
    inference_run: InferenceRun,
    w_max_override: dict[int, float] | None = None,
) -> FilterResult:
    """
    1. Load all predictions for this inference_run
    2. Load latest backtest_metrics for each ticker in the predictions
    3. Load per-universe W_max from conformal artifact (or use override)
    4. For each (ticker, horizon) triple:
       a. Check conviction > 67
       b. Check predicted_return > 0
       c. Count backtest strategies with passed=True → >= 2
       d. Check conformal width = (pred_hi - pred_lo) < W_max[horizon]
    5. Collect passing (ticker, horizon) pairs
    6. Snapshot thresholds into FilterRun
    7. Return FilterResult with passes + snapshot
    """

class FilterResult:
    passes: list[PassingTriple]  # (ticker_id, horizon, pred, conviction, width, backtest_passes)
    filter_run: FilterRun
    num_evaluated: int
    num_passed: int
```

**W_max loading**: `_load_w_max_from_artifact(session, universe_id) -> dict[int, float]` — reads conformal artifact's `model_metadata.w_max`. If not present, uses `w_max_override` or raises `FilterError("W_max not available for universe")`.

**Conformal width**: For horizon h, `width = pred_hi_t{h} - pred_lo_t{h}` from Prediction row. Compare against `W_max[h]`.

**Threshold snapshot**: Store in `filter_runs.filter_config`:
```json
{"conviction_threshold": 67, "backtest_pass_min": 2, "w_max": {"t1": 0.023, "t5": 0.041, ...}, "direction": "LONG"}
```

**Dependencies**: P5.T6.S1
**Effort**: M / 4 hrs
**Risk Flags**: W_max must come from SAME universe/model that produced the prediction (don't cross universes). If a ticker has no backtest, backtest_passes=0 → fails ≥2 criterion.
**Acceptance Criteria**:
- All P5.T6.S1 tests pass (GREEN)
- Reads per-universe W_max + freshest backtest results
- Missing-backtest ticker → 0 passes (not a crash); thresholds snapshotted
- `filter_runs.filter_config` records exact thresholds used

---

## Task P5.T7: Ticket Emission + Lifecycle + Daily Flow Wiring

**Feature**: Feature 7 — ticket emission
**Effort**: L / 2 days
**Dependencies**: P5.T6 (filter gate), S4 (daily inference flow)
**Risk Level**: Medium

### Sub-task P5.T7.S1: Implement Ticket Emission Service

**Description**: Turn passing (ticker, horizon) pairs from the filter into conviction_tickets with calendar-correct resolution dates.

**Files to create**:
- `backend/app/features/conviction_tickets/repository.py` — DB persistence for tickets + filter_runs
- `backend/app/features/conviction_tickets/service.py` — emission service

**Emission service**:
```python
async def emit_tickets(
    session: AsyncSession,
    filter_result: FilterResult,
    inference_run: InferenceRun,
) -> list[ConvictionTicket]:
    """
    For each passing (ticker_id, horizon) pair:
    1. Get resolution_date = inference_date + horizon trading days via calendar
    2. Build ConvictionTicket with status=TRADABLE
    3. Copy pred/conformal/conviction/backtest data from prediction + filter
    4. Compute expires_at = resolution_date market close
    5. Upsert via UNIQUE(inference_run_id, ticker_id, horizon) — idempotent
    """
```

**Resolution date**: Use the trading calendar from S2. `T+5` = 5 NYSE trading sessions forward from `inference_date`.
```python
sessions = trading_days(inference_date, inference_date + timedelta(days=30))
resolution_date = sessions[horizon_days]  # 1, 5, 10, or 15
```

**Idempotency**: The `UNIQUE(inference_run_id, ticker_id, horizon)` constraint prevents duplicates. Use `insert(...).on_conflict_do_nothing()` in the repository.

**Filter run recording**:
```python
async def create_filter_run(session, inference_run_id, backtest_run_id, num_evaluated, num_emitted, config) -> FilterRun
```

**Dependencies**: P5.T6.S2, S2 (trading calendar)
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- Passing pairs become TRADABLE tickets with calendar-correct resolution dates
- Emission idempotent (re-running same inference run doesn't duplicate)
- `filter_run` records evaluated + emitted counts
- Tickets carry all required fields: predicted_return, conviction, conformal bounds, backtest passes/strategies

### Sub-task P5.T7.S2: Implement Ticket Lifecycle Endpoints

**Description**: User-driven lifecycle transitions + state machine validation.

**Files to create**:
- `backend/app/features/conviction_tickets/schemas.py` — Pydantic v2 request/response schemas
- `backend/app/features/conviction_tickets/endpoints/__init__.py`
- `backend/app/features/conviction_tickets/endpoints/lifecycle.py`
- `backend/app/features/conviction_tickets/endpoints/tickets.py` — query endpoints
- `backend/app/features/conviction_tickets/router.py`
- `backend/app/features/conviction_tickets/dependencies.py`

**Endpoints**:
```python
POST /api/v1/tickets/{id}/review    # TRADABLE → REVIEWED (any authenticated)
POST /api/v1/tickets/{id}/action    # → ACTIONED (any authenticated, optional notes)
GET  /api/v1/tickets                # List all TRADABLE tickets (inbox query)
GET  /api/v1/tickets/{id}           # Ticket detail
GET  /api/v1/tickets/history        # Chronological with status/outcome filters
GET  /api/v1/tickets/export.csv     # CSV export (10K cap)
```

**State machine validation**:
```python
VALID_TRANSITIONS = {
    "TRADABLE": {"REVIEWED", "ACTIONED", "EXPIRED"},
    "REVIEWED": {"ACTIONED", "EXPIRED", "RESOLVED"},
    "ACTIONED": {"RESOLVED"},
    "RESOLVED": set(),   # terminal
    "EXPIRED": set(),     # terminal
}
```

**Action notes**: `POST /tickets/{id}/action` accepts `{"notes": "optional text"}`.
**Error response for invalid transition**: `{"error_code": "INVALID_TRANSITION", "message": "Cannot transition from RESOLVED to REVIEWED"}`.

**Dependencies**: P5.T7.S1
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- Review/action transitions work with validation
- Illegal transitions rejected with clear error
- ACTIONED tickets carry optional user_notes
- Ticket list/filter endpoints support inbox query patterns

### Sub-task P5.T7.S3: Wire Filter + Emission into Daily Inference Flow

**Description**: Extend S4's daily_inference flow to include filter → emission after predictions are written.

**Files to modify**:
- `backend/app/orchestration/flows/daily_inference.py` — add filter + emission tasks

**Changes** (add tasks downstream of `infer_for_universe`):
```python
@task(retries=1, timeout_seconds=300)
async def filter_and_emit(inference_run_id, universe_id):
    async with get_session() as session:
        inference_run = await get_inference_run(session, inference_run_id)
        filter_result = await apply_filter(session, inference_run)
        tickets = await emit_tickets(session, filter_result, inference_run)
        return len(tickets)

@flow(name="daily_inference")
async def daily_inference_flow():
    ...
    for u in universes:
        run = await infer_for_universe(u.id)
        n_tickets = await filter_and_emit(run.id, u.id)  # NEW
```

**Per-universe isolation**: Filter/emission failure for one universe doesn't block others. Filter failure doesn't corrupt written predictions (they're already upserted).

**Dependencies**: P5.T7.S1, P4.T11.S2 (daily_inference)
**Effort**: S / 3 hrs
**Acceptance Criteria**:
- Daily flow emits tickets after inference, reading freshest backtests
- Per-universe isolation; failure in filtering doesn't corrupt written predictions
- End-to-end daily run produces TRADABLE tickets

---

## Task P5.T8: Outcome Resolution Flow

**Feature**: Feature 7 + Feature 9 — outcome tracking
**Effort**: M / 1 day
**Dependencies**: P5.T7 (tickets exist), S2 (ohlcv_bars, calendar)
**Risk Level**: Medium — **THE correctness crux** (R4)

### Critical: Base vs Resolution Close Attribution

The plan design is exact:
- **Base close** = close price on `inference_date` (the day the prediction was made)
- **Resolution close** = close price on `resolution_date` (the horizon end date)
- `actual_return = close[resolution_date] / close[inference_date] - 1`
- Getting these swapped would invert every single win/loss

### Sub-task P5.T8.S1: Implement Outcome Resolution Service

**Description**: Compute actual returns and resolve ticket outcomes.

**Files to create**:
- `backend/app/features/conviction_tickets/resolution/__init__.py`
- `backend/app/features/conviction_tickets/resolution/service.py`

**Implementation**:
```python
async def resolve_tickets(session: AsyncSession, as_of_date: date | None = None) -> ResolutionResult:
    """
    1. Query tickets WHERE resolution_date <= today AND status IN ('TRADABLE','REVIEWED','ACTIONED')
       (use idx_tickets_resolution index)
    2. For each ticket:
       a. Get close[inference_date] from ohlcv_bars for the ticker
       b. Get close[resolution_date] from ohlcv_bars for the ticker
       c. If resolution_date bar not ingested yet → skip (defer, don't error)
       d. If resolution_date is not a trading day → use next available trading day
       e. actual_return = close_resolution / close_base - 1  (LONG-only)
       f. outcome: 'win' if actual_return > 0, 'loss' if < 0, 'flat' if |return| < 0.001
       g. Transition: TRADABLE/REVIEWED → RESOLVED; ACTIONED → RESOLVED (preserve actioned flag)
    3. For TRADABLE tickets where resolution_date < today and still TRADABLE → EXPIRED
    4. Idempotent: skip already RESOLVED/EXPIRED tickets
    """
```

**Calendar alignment**: Use `is_trading_day()` from S2. If resolution_date falls on a non-trading day, use `trading_days(resolution_date, resolution_date + timedelta(days=7))[0]` as the actual resolution date.

**Missing bar deferral**: If `get_bar(session, ticker_id, resolution_date)` returns None → log warning, skip ticket (don't error). The ticket will be picked up on the next resolution sweep.

**Idempotency**: Only process tickets where status is NOT RESOLVED/EXPIRED. Re-running won't double-resolve.

**Dependencies**: P5.T7.S1, S2 (ohlcv_bars repository, trading calendar)
**Effort**: M / 4 hrs
**Risk Flags**: Base/resolution close attribution is THE correctness crux. Triple-check. The test must verify win/loss/flat outcomes against known price fixtures.
**Acceptance Criteria**:
- actual_return computed from correct base/resolution closes
- outcome (win/loss/flat) + status transitions correct; ACTIONED preserved
- Idempotent; missing resolution-bar deferred not errored
- Calendar-aligned dates; non-trading-day resolution rolls to next session

### Sub-task P5.T8.S2: Implement the Outcome Resolution Prefect Flow

**Description**: Build the daily resolution flow, scheduled weekdays 5:00pm ET.

**File to create**: `backend/app/orchestration/flows/outcome_resolution.py`

**Flow structure**:
```python
@flow(name="outcome_resolution")
async def outcome_resolution_flow():
    async with get_session() as session:
        result = await resolve_tickets(session, as_of_date=date.today())
    # Log: resolved N, expired M, deferred K
    # After resolution, trigger coverage computation (S6 or inline)
```

**Schedule**: Weekdays 5:00pm ET (after market close, before daily inference at 5:30pm).
**Registration**: Add to `orchestration/deployments.py`.

**Coverage feed**: After resolving, the coverage tracker (`conformal/coverage_tracker.py`) can compute realized coverage. Wire this in or leave for S6's monitoring flow. For S5, just ensure resolved outcomes are recorded and queryable.

**Dependencies**: P5.T8.S1, P2.T3.S2
**Effort**: S / 3 hrs
**Acceptance Criteria**:
- Resolution flow deployed + scheduled (weekdays after close) + on-demand
- Due tickets resolved; stale TRADABLE expired
- Resolved outcomes available for coverage measurement

---

## Task P5.T9: Conviction Ticket Inbox/Detail + Backtest Explorer UI

**Feature**: Features 6 + 7 — frontend
**Effort**: XL / 3 days
**Dependencies**: P5.T4 (backtest API), P5.T7 (ticket API)
**Risk Level**: Low

### Frontend Conventions (from existing code)
- TanStack Query v5 with query key factories
- Zustand for auth token (auth store)
- shadcn/ui + Tailwind CSS
- TradingView Lightweight Charts for financial series
- React Router v6
- TypeScript strict mode
- Polling: `refetchInterval` per surface

### Sub-task P5.T9.S1: Build the Conviction Ticket Inbox

**Description**: The headline view — all TRADABLE tickets in a TanStack Table.

**Files to create**:
- `frontend/src/features/conviction_tickets/api/useTickets.ts` — TanStack Query hooks
- `frontend/src/features/conviction_tickets/pages/InboxPage.tsx`
- `frontend/src/features/conviction_tickets/components/ConvictionBadge.tsx`
- `frontend/src/features/conviction_tickets/components/ConformalIntervalBar.tsx`

**Inbox features**:
- TanStack Table: sortable (conviction desc default), filterable
- Filters: universe dropdown, horizon (T1/T5/T10/T15), conviction range slider, backtest-pass-count (2/3/4), conformal-width range
- Each row: ticker symbol, universe, horizon badge, conviction score (color-coded), predicted return %, conformal interval [low, high], backtest passes (X/4 badges), status badge
- Filters map to URL query params (shareable state)
- 60s refetch interval (polling)
- Click row → navigate to `/tickets/{id}`

**API types** (generate from backend schemas):
```typescript
interface TicketListItem {
  id: string;
  ticker: { id: string; symbol: string };
  universe: { id: string; name: string };
  horizon: "T1" | "T5" | "T10" | "T15";
  conviction_score: number;
  predicted_return: number;
  conformal_lower: number;
  conformal_upper: number;
  backtest_passes: number;
  backtest_pass_strategies: string[];
  status: string;
  resolution_date: string;
}
```

**Dependencies**: P5.T7.S1 (ticket endpoints), P0.T8 (frontend infra)
**Effort**: L / 1 day
**Acceptance Criteria**:
- Inbox lists TRADABLE tickets, sortable + filterable per design
- Conviction color-coded badge (0-44 red, 45-55 yellow, 56-69 light-green, 70-100 green)
- Conformal interval visually rendered as a bar
- Filters reflected in URL state
- 60s auto-refetch

### Sub-task P5.T9.S2: Build the Ticket Detail View

**Description**: Full breakdown per ticket with action buttons.

**Files to create**:
- `frontend/src/features/conviction_tickets/api/useTicket.ts`
- `frontend/src/features/conviction_tickets/api/useTicketActions.ts` — review, action mutations
- `frontend/src/features/conviction_tickets/pages/DetailPage.tsx`
- `frontend/src/features/conviction_tickets/components/BacktestPassTable.tsx`
- `frontend/src/features/conviction_tickets/components/EnsembleBreakdown.tsx`

**Detail view sections**:
1. **Header**: Ticker symbol, universe, horizon, status badge, conviction score with visual gauge
2. **Ensemble Math**: LSTM vs TFT component breakdown (from prediction's raw arrays) — lstm_outputs vs tft_q50 per horizon
3. **Conformal Interval**: Visual bar showing [low, predicted, high] with alpha=0.10 annotation
4. **Backtest Evidence**: Table showing 4 strategies with pass/fail + per-strategy metrics when expanded
5. **Link to Feature Snapshot**: `→` link to `/features/inspect?ticker=X&date=Y` (S3 inspect page)
6. **Action Buttons**: "Mark Reviewed" (TRADABLE→REVIEWED), "Mark Actioned + notes" (→ACTIONED)
7. **Lifecycle Timeline**: Visual state progression

**Action mutations** (optimistic updates via TanStack Query):
```typescript
const reviewMutation = useMutation({
  mutationFn: (id) => apiClient.post(`/api/v1/tickets/${id}/review`),
  onMutate: async (id) => { /* optimistic: update cache to REVIEWED */ },
  onError: (_, __, context) => { /* rollback */ },
})

const actionMutation = useMutation({
  mutationFn: ({id, notes}) => apiClient.post(`/api/v1/tickets/${id}/action`, {notes}),
  // Similar optimistic pattern
})
```

**Dependencies**: P5.T9.S1, P5.T7.S2 (lifecycle endpoints)
**Effort**: L / 1 day
**Acceptance Criteria**:
- Detail shows ensemble components, conformal viz, backtest-by-strategy table
- Action buttons transition state with optimistic UI
- Links to feature-inspect snapshot
- Invalid transitions show inline error (e.g., can't review an EXPIRED ticket)

### Sub-task P5.T9.S3: Build Ticket History + CSV Export + Backtest Explorer

**Description**: History view, export, and the backtest explorer UI.

**Files to create**:
- `frontend/src/features/conviction_tickets/pages/HistoryPage.tsx`
- `frontend/src/features/conviction_tickets/api/useTicketHistory.ts`
- `frontend/src/features/conviction_tickets/api/useExportCsv.ts`
- `frontend/src/features/backtesting/` — full frontend feature directory
- `frontend/src/features/backtesting/api/useBacktestSummary.ts`
- `frontend/src/features/backtesting/api/useBacktestDetail.ts`
- `frontend/src/features/backtesting/pages/ExplorerPage.tsx`
- `frontend/src/features/backtesting/pages/TickerDetailPage.tsx`
- `frontend/src/features/backtesting/components/PassBadgeGrid.tsx`
- `frontend/src/features/backtesting/components/EquityCurveChart.tsx`
- `frontend/src/features/backtesting/components/DrawdownChart.tsx`

**History page**: Reuses the inbox table component with additional status/outcome filters and chronological ordering.

**CSV export**: `GET /api/v1/tickets/export.csv?universe_id=X&status=TRADABLE` → triggers browser download with 10K row cap.

**Backtest explorer** (`/backtests/{universe_id}`):
- Pass badge grid: each ticker shows 4 colored dots (green=pass, red=fail)
- Click ticker → navigate to ticker detail

**Backtest ticker detail** (`/backtests/{universe_id}/{ticker_id}`):
- 4 equity curve charts via TradingView Lightweight Charts (one per strategy)
- 1 drawdown chart via Recharts (overlaid drawdowns)
- 6-metric table per strategy
- Backtest period info

**Chart implementation** (TradingView Lightweight Charts):
```typescript
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';

// Render equity curve data: [{date: "2024-01-02", value: 100000}, ...]
chart.addLineSeries({ color: '#26a69a', lineWidth: 1 });
```

**Dependencies**: P5.T9.S2, P5.T4.S2 (backtest endpoints)
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- History view with outcome filters; CSV export works (capped)
- Backtest explorer shows pass badges + per-ticker equity/drawdown charts + 6 metrics
- Equity curves render via TradingView Lightweight Charts
- Navigation between views works (inbox → detail → backtest → feature inspect)

### Sub-task P5.T9.S4: Add Frontend Routes

**Files to modify**: `frontend/src/App.tsx` — add new routes

**New routes**:
```typescript
<Route path="/tickets" element={<ProtectedRoute><InboxPage /></ProtectedRoute>} />
<Route path="/tickets/history" element={<ProtectedRoute><HistoryPage /></ProtectedRoute>} />
<Route path="/tickets/:id" element={<ProtectedRoute><DetailPage /></ProtectedRoute>} />
<Route path="/backtests/:universeId" element={<ProtectedRoute><ExplorerPage /></ProtectedRoute>} />
<Route path="/backtests/:universeId/:tickerId" element={<ProtectedRoute><TickerDetailPage /></ProtectedRoute>} />
```

**Effort**: S / 1 hr (after components built)

---

## Task P5.T10: Integration + E2E + Docs

**Feature**: Cross-feature verification
**Effort**: M / 1 day
**Dependencies**: P5.T7 (emission), P5.T8 (resolution), P5.T9 (UI)
**Risk Level**: Low

### Sub-task P5.T10.S1: Cross-Feature Integration Tests

**Description**: Test the full output path on synthetic data.

**Files to create**:
- `backend/app/features/conviction_tickets/tests/__init__.py`
- `backend/app/features/conviction_tickets/tests/test_integration.py`
- `backend/app/features/backtesting/tests/__init__.py`
- `backend/app/features/backtesting/tests/test_integration.py`

**Test scenarios**:
1. **Full path E2E**: Seed predictions + backtest_metrics → apply_filter → assert correct ticket count → emit_tickets → transition one to ACTIONED → resolve outcomes → assert win/loss/flat correct
2. **Filter criteria gate**: Each criterion boundary tested end-to-end
3. **Idempotency**: Re-run emission → no duplicates; re-run resolution → no double-resolve
4. **Missing backtest**: Ticker with predictions but no backtest_metrics → no tickets emitted
5. **Outcome resolution correctness**: Seed known close prices → assert actual_return computed correctly

**Test DB**: Uses the existing `conftest.py` testcontainers Postgres+TimescaleDB infrastructure.

**Dependencies**: P5.T7, P5.T8
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- Full path (predict → backtest → filter → emit → resolve) tested
- Filter criteria gate correctly; resolution attributes returns correctly
- Idempotency of emission + resolution asserted
- Missing-edge-case coverage

### Sub-task P5.T10.S2: Extend Playwright E2E

**Description**: End-to-end browser test for the headline user journey.

**Files to create/modify**: Under `frontend/e2e/` (create if not existing)

**Test scenario**:
```typescript
test('ticket inbox → detail → mark actioned', async ({ page }) => {
  // 1. Log in
  // 2. Navigate to /tickets
  // 3. Assert seeded TRADABLE tickets render in inbox
  // 4. Click first ticket → navigate to /tickets/{id}
  // 5. Assert detail components render (conviction, conformal, backtest table)
  // 6. Click "Mark Reviewed" → assert status updates to REVIEWED
  // 7. Click "Mark Actioned" with notes → assert status updates to ACTIONED
});
```

**Seed data**: Create deterministic tickets via a fixture/script in the test compose environment. Reuse `/ready` wait-gate pattern.

**Dependencies**: P5.T9.S2, P0.T9.S3
**Effort**: M / 4 hrs
**Acceptance Criteria**:
- E2E passes: inbox renders → open detail → mark reviewed → mark actioned → status updates
- Deterministic seeded tickets; `/ready` wait-gate used
- Fails if ticket rendering or lifecycle breaks

### Sub-task P5.T10.S3: Features.md Documentation

**Description**: Write developer documentation for both new features.

**Files to create**:
- `backend/app/features/backtesting/features.md`
- `backend/app/features/conviction_tickets/features.md`
- `frontend/src/features/backtesting/feature.md`
- `frontend/src/features/conviction_tickets/feature.md`

**Backtesting features.md must document**:
- The 4 strategies with entry/exit formulas
- Vectorbt engine params (init_cash, fees, risk_free)
- Pass criteria (locked: sharpe > 1.5, trades ≥ 10, drawdown > -0.40)
- Active-member scope (locked deviation)
- Signal-timing protection (S3 feature reuse + previous-bar crossover)
- API endpoints

**Conviction tickets features.md must document**:
- The 4-criteria filter gate with exact thresholds
- W_max sourcing (per-universe, from conformal artifact metadata)
- Filter-in-daily-flow orchestration (locked decision)
- Ticket lifecycle state machine
- Outcome resolution: base/resolution close attribution, calendar alignment, idempotency
- Multi-horizon independence
- Output contract for Pipeline B consumption

**Dependencies**: P5.T9, P5.T8
**Effort**: S / 3 hrs
**Acceptance Criteria**:
- Both features.md document the implemented behavior + locked decisions
- W_max sourcing + lifecycle + daily-flow wiring clearly explained
- Output contract documented for future Pipeline B consumption

---

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Owner Task |
|----|------|-----------|--------|------------|------------|
| R0 | **W_max not stored** — Filter gate can't compute width threshold | High (confirmed) | High | P5.T0 retroactive backfill: add `compute_W_max()` to calibrator, patch `train_universe()`, store in artifact metadata | P5.T0 |
| R1 | **Signal-timing lookahead** — entries/exits using same-bar data | Medium | High | Reuse S3 lookahead-audited features; previous-bar crossover for MomentumCross; per-strategy fixture tests; no `close.shift(-1)` anywhere | P5.T2 |
| R2 | **StatArb date misalignment** — asset/SPY dates shifted | Medium | Medium | Explicit date alignment in orchestrator; cointegrated fixture test; SPY loaded once and joined on date index | P5.T2.S3, P5.T4.S1 |
| R3 | **Filter emits flood or nothing** — thresholds wrong | Medium | Medium | Per-universe adaptive W_max (P5.T0); threshold snapshot in filter_runs; independently re-runnable filter step | P5.T6.S2 |
| R4 | **Outcome resolution mis-attributes returns** — wrong base/resolution close | Medium | **High** | Calendar-aligned dates; base=inference_date close, resolution=resolution_date close; idempotent; defer missing bars; extensive fixture tests | P5.T8.S1 |
| R5 | **Zero-trade strategy crashes engine** | Low | Medium | No-trades → empty_metrics → passed=False; zero-loss → handled profit_factor | P5.T3.S1 |
| R6 | **Newly-added ticker has no backtest** | Medium | Low | Backtest_passes = 0 (fails ≥2 criterion), not a crash | P5.T6.S2 |
| R7 | **Duplicate tickets on re-run** | Low | Medium | UNIQUE(inference_run_id, ticker_id, horizon) + on_conflict_do_nothing | P5.T7.S1 |
| R8 | **vectorbt Python 3.12 incompatibility** | High | High | vectorbt requires Python 3.11; if backend uses 3.12+, use subprocess approach or pure-python metrics fallback | P5.T3.S1 |
| R9 | **TFT graceful degradation** — conviction computed with narrower LSTM-only spreads | Medium | Low | LSTM-only spreads → conviction scores valid [0,100]; filter gate does not depend on TFT specifically; documented caveat | P5.T6, P5.T7 |

---

## Assumptions Log

Inherited from `tech-stack-analysis.md` §4, plus S5-specific:

- **Backtest scope** is active members per universe, weekly (locked); point-in-time historical backtests are future upgrade.
- **Filter orchestration** reuses daily-inference flow (locked): predictions → filter (reads freshest backtests) → tickets; weekly backtest runs independently before retrain.
- **W_max is per-universe**, computed from calibration set at train time (90th-pct conformal width), stored on conformal artifact metadata, user-overridable later (locked).
- **Strategies read pre-computed technical features from S3** (lookahead-audited), not recomputed.
- **Long-only filter** for v1 (predicted_return > 0); SHORT reserved.
- **Block A7 pass criteria**: Sharpe > 1.5 AND total_trades ≥ 10 AND max_drawdown > −0.40 (deviation #11).
- **Python 3.12+ backend** — vectorbt subprocess fallback may be needed.
- **Predictions table is NOT a hypertable** (S4 deviation DEV4) — this is acceptable for S5 filter queries as we query by inference_run_id.
- **TFT may be in graceful-degradation mode** — conviction scoring still works with LSTM-only spreads; filter doesn't depend on TFT specifically.

---

## Exit Criteria

- [ ] P5.T0: W_max computed and stored on conformal artifact metadata
- [ ] P5.T1: All 4 tables created with indexes and generated column
- [ ] P5.T2: 4 strategies pass all TDD tests; no lookahead
- [ ] P5.T3: MetricsEngine extracts 6 metrics + equity curves; edge cases handled
- [ ] P5.T4: BacktestOrchestrator runs all active members × 4 strategies; API endpoints work
- [ ] P5.T5: Weekly backtest flow deployed and scheduled
- [ ] P5.T6: Filter gate applies 4 criteria correctly; W_max sourced per-universe
- [ ] P5.T7: Ticket emission idempotent; lifecycle transitions validated; daily flow wired
- [ ] P5.T8: Outcome resolution attributes returns correctly; idempotent; flow scheduled
- [ ] P5.T9: Inbox/detail/history/explorer UI renders; filters work; charts render
- [ ] P5.T10: Integration tests pass; E2E passes; features.md written
- [ ] All backend tests GREEN
- [ ] Frontend tests GREEN
- [ ] TypeScript strict: no errors
- [ ] Ruff lint: no errors
- [ ] CI green

---

## Appendix: Key File Paths Reference

### Backend — New Files

```
backend/app/features/backtesting/
├── __init__.py
├── models.py                    # BacktestRun, BacktestMetrics ORM
├── schemas.py                   # Pydantic v2 schemas
├── repository.py                # Async DB persistence
├── service.py                   # BacktestOrchestrator
├── router.py                    # FastAPI APIRouter
├── dependencies.py
├── features.md                  # Developer docs
├── endpoints/
│   ├── __init__.py
│   └── backtest.py              # Trigger, universe view, ticker detail endpoints
├── shared/
│   ├── __init__.py
│   ├── base.py                  # BaseStrategy ABC
│   ├── metrics_engine.py        # VectorBT MetricsEngine
│   └── tests/
│       ├── __init__.py
│       └── test_metrics_engine.py
├── strategies/
│   ├── __init__.py
│   ├── mean_reversion.py
│   ├── momentum_cross.py
│   ├── volatility_breakout.py
│   ├── stat_arb.py
│   └── tests/
│       ├── __init__.py
│       ├── test_mean_reversion.py
│       ├── test_momentum_cross.py
│       ├── test_volatility_breakout.py
│       └── test_stat_arb.py
└── tests/
    ├── __init__.py
    └── test_integration.py

backend/app/features/conviction_tickets/
├── __init__.py
├── models.py                    # ConvictionTicket, FilterRun ORM
├── schemas.py                   # Pydantic v2 schemas
├── repository.py                # Async DB persistence
├── service.py                   # Ticket emission + lifecycle service
├── router.py                    # FastAPI APIRouter
├── dependencies.py
├── features.md                  # Developer docs
├── endpoints/
│   ├── __init__.py
│   ├── tickets.py               # List, detail, history, CSV export
│   └── lifecycle.py             # Review, action transitions
├── filter/
│   ├── __init__.py
│   ├── gate.py                  # apply_filter() — 4-criteria gate
│   └── tests/
│       ├── __init__.py
│       └── test_gate.py         # 8+ filter boundary tests
├── resolution/
│   ├── __init__.py
│   └── service.py               # resolve_tickets() — outcome resolution
└── tests/
    ├── __init__.py
    └── test_integration.py

backend/app/orchestration/flows/
├── weekly_backtest.py           # NEW: Sunday 4am ET
└── outcome_resolution.py        # NEW: Weekdays 5pm ET

backend/app/orchestration/flows/daily_inference.py  # MODIFY: add filter+emit tasks

backend/alembic/versions/
└── c1d2e3f4a5b6_add_backtesting_conviction_tickets_tables.py  # NEW migration
```

### Backend — Modified Files

```
backend/app/features/ml_models/conformal/calibrator.py          # ADD: compute_W_max()
backend/app/features/ml_models/conformal/tests/test_calibrator.py  # ADD: 2 W_max tests
backend/app/features/ml_models/service.py                        # MODIFY: store W_max in metadata
backend/app/features/ml_models/inference_service.py              # ADD: _load_w_max() helper
backend/app/features/ml_models/tests/test_training_pipeline.py  # EXTEND: assert W_max stored
backend/alembic/env.py                                          # MODIFY: import new models
backend/app/app.py                                               # MODIFY: register new routers
backend/app/orchestration/deployments.py                        # MODIFY: register weekly_backtest + outcome_resolution
backend/pyproject.toml                                           # MODIFY: add vectorbt dependency
```

### Frontend — New Files

```
frontend/src/features/conviction_tickets/
├── feature.md
├── api/
│   ├── useTickets.ts
│   ├── useTicket.ts
│   ├── useTicketHistory.ts
│   ├── useTicketActions.ts
│   └── useExportCsv.ts
├── pages/
│   ├── InboxPage.tsx
│   ├── DetailPage.tsx
│   └── HistoryPage.tsx
└── components/
    ├── ConvictionBadge.tsx
    ├── ConformalIntervalBar.tsx
    ├── BacktestPassTable.tsx
    └── EnsembleBreakdown.tsx

frontend/src/features/backtesting/
├── feature.md
├── api/
│   ├── useBacktestSummary.ts
│   └── useBacktestDetail.ts
├── pages/
│   ├── ExplorerPage.tsx
│   └── TickerDetailPage.tsx
└── components/
    ├── PassBadgeGrid.tsx
    ├── EquityCurveChart.tsx
    └── DrawdownChart.tsx
```

### Frontend — Modified Files

```
frontend/src/App.tsx  # ADD: new routes for /tickets/* and /backtests/*
```

---

## End of Stage S5 Plan

