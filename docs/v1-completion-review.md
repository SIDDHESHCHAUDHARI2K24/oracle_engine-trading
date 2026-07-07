# Pipeline A v1 — Completion Review

> **Date**: July 2026
> **Scope**: All 9 features, cross-cutting concerns, 12 spec deviations, and Pipeline B handoff

---

## Feature Completion Status

| # | Feature | Sprint | Status | Notes |
|---|---|---|---|---|
| 1 | Auth & User Accounts | S1 | Done | JWT + refresh tokens, single admin, argon2 hashing, rate limiting, `scripts/seed_admin.py`, `scripts/reset_password.py` |
| 2 | Universe Management | S1 | Done | S&P 500, Russell 1000, Russell 2000 seeded; time-aware memberships; CRUD API; `seed_universes.py` |
| 3 | Data Ingestion (Block A1) | S2 | Done | yfinance → Alpaca → Stooq failover; FRED macro (7 series); TimescaleDB hypertables; idempotent upsert; `initial_backfill.py` |
| 4 | Feature Engineering (Blocks A2 + A3) | S3 | Done | 31-dim feature tensor; TA-Lib + pandas; rolling Z-score normalization; 4-horizon continuous targets; burn-in period handling |
| 5 | ML Models (Blocks A4, A5, A6) | S4 | Done | Bi-LSTM (3×128 + attention); TFT Quad-Array (4 per universe); HuberLoss + QuantileLoss; walk-forward 70/15/15 split; locally-weighted split conformal; champion/challenger promotion |
| 6 | Backtesting (Block A7) | S5 | Done | 4-strategy vectorized backtester (mean reversion, momentum cross, volatility breakout, stat arb); vectorbt engine; filter-pass criteria (Sharpe > 1.5, trades ≥ 10, max DD > -40%) |
| 7 | Conviction Tickets (Block A8) | S5 | Done | Filter gate (conviction > 67, return > 0, backtest ≥ 2, conformal width < W_max); multi-horizon; status lifecycle (TRADABLE → REVIEWED → ACTIONED → RESOLVED → EXPIRED); outcome resolution |
| 8 | Monitoring & Model Health | S6 | Done | 7 signals (coverage, drift, correlation, loss curve, freshness, pipeline success, backtest drift); alert system with Slack notifier; 8 alert codes; model health dashboard |
| 9 | Orchestration + Housekeeping | S6 | Done | 8 Prefect flows (daily refresh, daily inference, weekly retrain, weekly backtest, outcome resolution, coverage check, daily monitoring, artifact retention); TimescaleDB partition manager; session reaper |

---

## Cross-Cutting Deliverables

| Item | Sprint | Status | Notes |
|---|---|---|---|
| Frontend (React + TS strict) | S1-S6 | Done | Vite + React 18 + TanStack Query + Tailwind + shadcn/ui; TradingView charts; feature-mirrored structure |
| Playwright E2E suite | S6 | Done | Critical-path smoke tests covering login → universe → tickets flow |
| Runbooks | S6 | Done | 5 runbooks: cold-start-ingestion, quarterly-index-refresh, alert-response, monday-morning-digest, colab-training, prefect-flow-recovery, manual-password-reset |
| Feature docs (features.md) | S1-S6 | Done | Per-feature developer documentation: auth, universes, data_ingestion, feature_engineering, ml_models, backtesting, conviction_tickets, monitoring |
| Architecture doc | S6 | Done | `docs/architecture.md` — system overview, data flow, component map |
| Design doc | S0 | Done | `docs/mbi-pipeline-a-v1-design.md` — 1370-line locked decisions document |
| Development plans | S0 | Done | `features-to-develop/development-plan-S0.md` through `S6.md` |
| graphify knowledge graph | ongoing | Active | Auto-rebuilt on git commit; query-first search for agents |
| Agent instructions | S0 | Done | `agent-instructions/Pipeline-A-Agent-Instructions.md`, `Frontend-Agent-Instructions.md` |

---

## 12 Spec Deviations — All Implemented

| # | Deviation | Implemented In |
|---|---|---|
| 1 | LSTM: Sigmoid + BCELoss → Linear + HuberLoss | `ml_models/lstm/architecture.py` |
| 2 | TFT: Sigmoid on quantiles → raw quantile outputs | `ml_models/tft/architecture.py` |
| 3 | Hardcoded 60/40 blend → uncertainty-aware adaptive blending | `ml_models/ensemble/blender.py` |
| 4 | Isotonic calibration → locally-weighted split conformal | `ml_models/conformal/calibrator.py` |
| 5 | 80/20 train/val → 70/15/15 train/cal/val | `ml_models/trainer.py` |
| 6 | P(move) > 0.67 filter → 4-criterion filter gate | `conviction_tickets/filter/gate.py` |
| 7 | Undefined conviction score → Derivation A (risk-adjusted magnitude) | `conviction_tickets/scoring/risk_adjusted.py` |
| 8 | 4 isotonic models → 4 conformal quantiles + residual predictor MLP | `ml_models/conformal/calibrator.py` |
| 9 | LSTM input_size=31 preserved (ticker-agnostic global model) | `ml_models/lstm/architecture.py` |
| 10 | Polygon + Alpha Vantage deferred → yfinance + Alpaca + Stooq | `data_ingestion/shared/fetcher_base.py` |
| 11 | Sharpe > 1.5 only → added trades ≥ 10 + max DD > -40% | `backtesting/filter.py` |
| 12 | BCELoss alteration documented and approved | This document + design doc §14 |

---

## Pipeline B Handoff — Conviction Ticket Output Contract

Pipeline B (LLM Agent Swarm + Fusion Engine) consumes Pipeline A's output via the `conviction_tickets`
table and REST API. The contract:

### Data Shape

Each ticket Pipeline B will consume:

```json
{
  "id": "uuid",
  "inference_date": "2026-07-01",
  "ticker": { "id": "uuid", "symbol": "AAPL" },
  "universe": { "id": "uuid", "name": "sp500" },
  "horizon": "T1 | T5 | T10 | T15",
  "direction": "LONG",
  "predicted_return": 0.0184,
  "conviction_score": 76.4,
  "conformal_interval": { "low": 0.0053, "high": 0.0315, "alpha": 0.10 },
  "backtest_passes": 3,
  "backtest_pass_strategies": ["mean_reversion", "momentum_cross", "stat_arb"],
  "status": "TRADABLE",
  "resolution_date": "2026-07-06",
  "actual_return": null,
  "outcome": null
}
```

### API Endpoints Pipeline B Should Use

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/tickets?status=TRADABLE` | Fetch all active tickets (the inbox) |
| `GET` | `/api/v1/tickets/{id}` | Full detail including ensemble math breakdown |
| `GET` | `/api/v1/tickets/history?outcome=win` | Historical tickets for back-analysis |
| `GET` | `/api/v1/features/inspect?ticker=AAPL&date=2026-07-01` | Debug: 31 feature values on a given day |

### Polling Pattern

Pipeline B should poll `/api/v1/tickets?status=TRADABLE` daily after the 5:30pm ET inference run
completes (check `inference_runs` for today's date with status `succeeded`).

### Outcome Feedback Loop

As Pipeline B trades on tickets, it should write outcomes back:
- Update `conviction_tickets.status = 'ACTIONED'` when a position is taken
- The daily `outcome_resolution` flow will set `actual_return` and `outcome` after the horizon resolves
- Pipeline B can consume `GET /api/v1/tickets/history?outcome=win&outcome=loss` for P&L tracking
