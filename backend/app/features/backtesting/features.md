# Backtesting — Feature Documentation

## Overview

Block A7 — the empirical proving ground that validates tickers before they
become conviction tickets. Runs 4 trading strategies per ticker against
pre-computed technical features, computes VectorBT performance metrics, and
stores pass/fail results keyed by strategy.

The backtesting layer is a pure research-validity gate, not a signal generator.
Strategies are intentionally simple and transparent.

## Architecture

```
BacktestOrchestrator
 ├── 4 BaseStrategy subclasses (MeanReversion, MomentumCross, VolatilityBreakout, StatArb)
 ├── MetricsEngine (VectorBT Portfolio.from_signals)
 └── Repository (BacktestRun + BacktestMetrics CRUD)
```

### Key Files

| File | Purpose |
|---|---|
| `models.py` | `BacktestRun` + `BacktestMetrics` ORM models |
| `service.py` | `BacktestOrchestrator` — per-ticker parallelization |
| `shared/base.py` | `BaseStrategy` ABC |
| `shared/metrics_engine.py` | VectorBT wrapper calculating Sharpe, drawdown, etc. |
| `repository.py` | Persistence layer — create run, upsert metrics, pass summaries |
| `schemas.py` | Pydantic v2 request/response schemas |
| `router.py` | FastAPI router at `/api/v1/backtests` |
| `endpoints/backtest.py` | Trigger + readback endpoints |

### ORM Models

**BacktestRun** — One per execution attempt:
- `universe_id`, `triggered_by`, `backtest_period_start/end`
- `status` (`running` → `completed` / `completed_with_errors` / `failed`)
- `num_tickers`, `num_strategies` (always 4), `metadata` (JSONB)

**BacktestMetrics** — One per (ticker, strategy) per run:
- `backtest_run_id`, `ticker_id`, `strategy_name`
- `sharpe_ratio`, `max_drawdown`, `total_return`, `win_rate`, `profit_factor`, `total_trades`
- `equity_curve` (JSONB array of {date, value})
- `passed` — GENERATED ALWAYS AS computed column (see Pass Criteria below)

## The 4 Strategies

All strategies read S3's pre-computed features from `feature_matrix`. No
indicator recomputation inside strategies (avoids lookahead + drift).

### MeanReversion
- **Entry**: `close < bb_lower`
- **Exit**: `close > bb_middle`
- **Features required**: `close`, `bb_lower`, `bb_middle`
- **File**: `strategies/mean_reversion.py:5`

### MomentumCross
- **Entry**: `sma_50` crosses above `sma_200` (previous-bar comparison)
- **Exit**: `sma_50` crosses below `sma_200`
- **Features required**: `close`, `sma_50`, `sma_200`
- **Lookahead protection**: `.shift(1)` ensures previous-bar crossover comparison,
  not current-bar. Zero future leakage.
- **File**: `strategies/momentum_cross.py:5`

### VolatilityBreakout
- **Entry**: `ATR > 1.25 * ATR_14_rolling_mean` AND `close > 20-day_high.shift(1)`
- **Exit**: `close < 0.95 * 20-day_high`
- **Features required**: `close`, `atr_14`
- **File**: `strategies/volatility_breakout.py:5`

### StatArb
- **Entry**: rolling 60-day OLS residual vs SPY < -2σ
- **Exit**: residual > -0.5σ
- **Features required**: `close`, `spy_close` (joined from OHLCV bars in orchestrator)
- **Edge cases**: < 61 rows → skip gracefully (no signals). NaN in spy slice → skip
  that row rather than aborting.
- **File**: `strategies/stat_arb.py:7`

## Pass Criteria (Locked)

The `backtest_metrics.passed` column is a **DB-level GENERATED ALWAYS AS** computed column:

```sql
COALESCE(sharpe_ratio, 0) > 1.5
  AND COALESCE(total_trades, 0) >= 10
  AND COALESCE(max_drawdown, -999) > -0.40
```

Three gates, all Boolean-AND:
1. **Sharpe ratio > 1.5** (risk-adjusted return floor)
2. **Total trades >= 10** (minimum statistical significance)
3. **Max drawdown > -0.40** (capital preservation floor)

This is a spec deviation: the original spec required only a Sharpe gate.
Trades and drawdown gates were added for statistical and risk-quality filtering.

## Metrics Engine

`MetricsEngine` wraps `vbt.Portfolio.from_signals()`:

- **Config**: `init_cash=$100K`, `fees=0.1%`, `risk_free=4.5%`, `freq=1D`
- **Computed metrics**: sharpe_ratio, max_drawdown, total_return, win_rate,
  profit_factor, total_trades
- **Equity curve**: `portfolio.value()` extracted as `[{date, value}]` JSON
- **Empty/no-trade fallback**: returns zeros + empty equity curve (never raises)

## Signal-Timing Protection

- All strategies reuse S3's **pre-computed, lookahead-audited** technical features
- No indicator recomputation inside any strategy (eliminates indicator drift)
- MomentumCross uses `.shift(1)` for previous-bar comparison
- VolatilityBreakout uses `.shift(1)` on the 20-day rolling high
- Verified by per-strategy lookahead tests in `strategies/tests/`

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/backtests/trigger` | admin | Trigger a backtest run (universe or single ticker) |
| GET | `/api/v1/backtests/{universe_id}` | any | Pass badge summary for latest run |
| GET | `/api/v1/backtests/{universe_id}/{ticker_id}` | any | Per-strategy detail + equity curves |

### Request/Response

**POST /trigger**:
- Body: `{universe_id, ticker_id?}` — omit `ticker_id` for full universe
- Response: `{backtest_run_id, status}`

**GET /{universe_id}**:
- Response: `UniversePassSummary {universe_id, run?, tickers: [{ticker_id, symbol, passes, strategies}]}`

**GET /{universe_id}/{ticker_id}**:
- Response: `TickerBacktestDetail {ticker_id, symbol, strategies: [{strategy_name, sharpe_ratio, ..., passed, equity_curve}]}`

## Orchestration

- **weekly_backtest** Prefect flow: Sundays 4am ET, before model retrain
- Active members per universe (S1 membership query)
- Per-ticker isolation: one ticker failure does not abort the run
- Results persist to `backtest_metrics` and are read by the A8 filter gate

## Locked Decisions

- **Backtest scope**: active members only. Point-in-time historical membership
  is future work (requires membership history tracking).
- **Strategies read S3 features**: indicator recomputation is prohibited inside
  strategies. Feature-drift vector eliminated.
- **Long-only**: all 4 strategies are long-only. Short-support is reserved for v2.
- **Pass criteria at DB level**: the `passed` column is a persisted computed
  column — cannot be overridden by application code.
- **Sharpe + trades + drawdown gates**: deviation #11 from original spec
  (Sharpe-only → triple gate).
