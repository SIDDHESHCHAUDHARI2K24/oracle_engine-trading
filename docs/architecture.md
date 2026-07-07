# Oracle Engine — System Architecture

## Overview

The MBI Labs Oracle Engine is a self-improving research-grade ML pipeline (Pipeline A) that ingests
OHLCV + macroeconomic data, engineers a 31-dimensional feature tensor per ticker per day, trains
Bi-LSTM and Temporal Fusion Transformer models per equity universe, calibrates predictions with
locally-weighted split conformal prediction, validates via four backtest strategies, and emits
filtered Conviction Tickets for human review.

---

## High-Level Data Flow

```
External Sources                     Internal Pipeline                        Output
─────────────────                    ─────────────────                       ──────
                                     
  Yahoo Finance ──┐                 ┌──────────────────┐
                  │                 │  Data Ingestion   │
  Alpaca ────────►├────────────────►│  (Block A1)       │──► ohlcv_bars (TimescaleDB)
                  │                 │  yfinance→Alpaca  │──► macro_observations
  Stooq ─────────┤                 │  →Stooq failover  │──► ingest_runs
                  │                 └────────┬─────────┘
  FRED ──────────┘                          │
                                            ▼
                                 ┌──────────────────────┐
                                 │ Feature Engineering   │
                                 │ (Blocks A2 + A3)      │
                                 │ 31-dim tensor         │──► feature_matrix (TimescaleDB)
                                 │ TA-Lib + rolling Z    │──► normalization_stats
                                 │ 4-horizon targets     │
                                 └──────────┬───────────┘
                                            │
                          ┌─────────────────┴─────────────────┐
                          ▼                                   ▼
              ┌──────────────────────┐          ┌──────────────────────┐
              │   ML Models           │          │   Backtesting         │
              │   (Blocks A4-A6)      │          │   (Block A7)          │
              │                       │          │                       │
              │   LSTM (Bi-LSTM       │          │   4 strategies:       │
              │    3×128+attention)   │          │   · MeanReversion     │
              │                       │          │   · MomentumCross     │
              │   TFT Quad-Array      │          │   · VolatilityBreakout│
              │    (4 per universe)   │          │   · StatArb           │
              │                       │          │                       │
              │   Ensemble Blender    │          │   vectorbt engine     │──► backtest_metrics
              │   (uncertainty-aware) │          │                       │
              │                       │          └───────────┬───────────┘
              │   Conformal Calibrator│                       │
              │   (locally-weighted)  │                       │
              │                       │                       │
              └───────────┬───────────┘                       │
                          │                                   │
                          └─────────────┬─────────────────────┘
                                        │
                                        ▼
                            ┌──────────────────────┐
                            │  Conviction Tickets   │
                            │  (Block A8)           │
                            │                       │
                            │  Filter Gate:         │
                            │  · conviction > 67    │──► conviction_tickets
                            │  · return > 0         │──► filter_runs
                            │  · backtest ≥ 2       │
                            │  · conformal width    │
                            │    < W_max            │
                            └──────────┬───────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │  Pipeline B      │
                              │  (Future)        │
                              │  LLM Agent Swarm │
                              │  Fusion Engine   │
                              └─────────────────┘
```

---

## Component Map

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vite + React 18)                 │
│  Auth │ Universes │ Model Health │ Backtests │ Tickets │ Inbox   │
│  TanStack Query v5 │ Tailwind + shadcn/ui │ TradingView Charts   │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTP REST (polling every 30-60s)
┌──────────────────────────────┴───────────────────────────────────┐
│                    BACKEND (FastAPI + SQLAlchemy 2.0 async)       │
│                                                                   │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐           │
│  │   Auth   │ │Universes │ │  Ingest   │ │ Features │           │
│  │ JWT+RT   │ │CRUD+mem  │ │A1: fetch  │ │A2+A3:    │           │
│  │ argon2   │ │berships  │ │+failover  │ │31-d tensor│          │
│  └──────────┘ └──────────┘ └───────────┘ └──────────┘           │
│                                                                   │
│  ┌──────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐          │
│  │ML Models │ │Backtesting│ │Conviction │ │Monitoring│          │
│  │A4-A6:    │ │A7: 4-strat│ │A8: filter │ │7 signals │          │
│  │LSTM+TFT  │ │vectorbt   │ │gate+ticket│ │+alerts   │          │
│  │+conformal│ │           │ │lifecycle  │ │          │          │
│  └──────────┘ └───────────┘ └───────────┘ └──────────┘          │
│                                                                   │
└──────────────────────────────┬───────────────────────────────────┘
                               │ asyncpg
                    ┌──────────┴──────────┐
                    │   PostgreSQL 16     │
                    │   + TimescaleDB     │
                    │   + Prefect schema  │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
   │ TimescaleDB  │  │ Application  │  │ Prefect 3        │
   │ hypertables  │  │ tables       │  │ flow metadata     │
   │ · ohlcv_bars │  │ · universes  │  │ · run history     │
   │ · macro_obs  │  │ · users      │  │ · schedules       │
   │ · features   │  │ · tickets    │  │ · task retries    │
   │ · predictions│  │ · artifacts  │  │                   │
   └──────────────┘  └──────────────┘  └──────────────────┘
```

---

## Orchestration (Prefect 3)

All scheduled work runs as Prefect flows. No business logic in flows — they call feature services.

| Flow | Schedule | Covers |
|---|---|---|
| `daily_data_refresh` | Weekdays 4:30pm ET | Ingest + feature engineering increment |
| `daily_inference` | Weekdays 5:30pm ET | Inference per universe → filter → emit tickets |
| `weekly_backtest` | Sundays 4am ET | 5-year backtest of all 4 strategies |
| `weekly_retrain` | Sundays 6am ET | Walk-forward train → champion promotion |
| `outcome_resolution` | Weekdays 5pm ET | Resolve tickets whose horizon ended |
| `conformal_coverage_check` | Daily 11pm ET | Compute realized coverage → alert if breached |
| `daily_monitoring` | Daily 10pm ET | Freshness, pipeline success, drift (Mon/Thu only) |
| `artifact_retention` | Sundays 11pm ET | Archive artifacts > 6 months old |

Background schedulers (in-process via FastAPI `lifespan`):
- **partition_manager**: Pre-create next month's TimescaleDB partitions
- **session_reaper**: Delete expired auth sessions hourly

---

## Data Model (Condensed)

```
users ───┬──── sessions
         │
         ├──── universes ──┬── universe_memberships ──── tickers ──┬── ohlcv_bars
         │                 │                                       │
         │                 ├── training_runs ──┬── model_artifacts │
         │                 │                   │                   │
         │                 ├── inference_runs ─┴── predictions ────┤
         │                 │                                       │
         │                 ├── backtest_runs ──── backtest_metrics │
         │                 │                                       │
         │                 ├── conviction_tickets ◄────────────────┘
         │                 │       │
         │                 │       └── filter_runs
         │                 │
         │                 ├── coverage_metrics
         │                 ├── feature_drift_metrics
         │                 └── system_alerts
         │
         └── feature_matrix ◄── (joins on ticker_id + bar_date)
              │
              └── normalization_stats

macro_observations (standalone, joined into feature_matrix by date)
```

---

## Artifact Storage

- `~/.mbi/artifacts/` — local filesystem for v1
- `ModelArtifact.artifact_path` points to `.pt` files (PyTorch state dicts) and `.json` (conformal
  quantiles, residual predictor weights)
- Swap point for S3/MinIO: `core/services/artifact_store.py`

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| One LSTM + 4 TFTs **per universe** | Universes have different characteristics; separate models capture universe-specific patterns |
| Continuous regression (not classification) | Predicts magnitude + direction; regression is the principled approach for return prediction |
| HuberLoss for LSTM | Robust to fat-tailed financial returns; outperforms MSE on outliers |
| Locally-weighted split conformal | Provides statistical coverage guarantees with adaptive interval widths |
| Uncertainty-aware blending | Uses TFT quantile spread as a regime signal, replacing hardcoded 60/40 weights |
| Polling everywhere | No SSE/WebSockets/webhooks in v1; TanStack Query `refetchInterval` per surface |
| Feature matrix materialized | Avoids recomputing 31 features twice (training + inference); TimescaleDB makes queries cheap |

---

## Technology Stack

| Layer | Stack |
|---|---|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.0 async, asyncpg |
| Database | PostgreSQL 16 + TimescaleDB 2.16 |
| ML | PyTorch 2.2+, pytorch-lightning, pytorch-forecasting, TA-Lib, scipy, vectorbt |
| Orchestration | Prefect 3 (self-hosted, same Postgres) |
| Artifacts | Local filesystem (`~/.mbi/artifacts/`); MinIO/S3-ready |
| Frontend | Vite + React 18 + TypeScript strict, Tailwind + shadcn/ui, TradingView Charts |
| Package mgmt | uv (Python), pnpm (Node) |
| Testing | pytest + pytest-asyncio, vitest + testing-library, Playwright (E2E) |
| Linting | ruff (Python), ESLint + Prettier (TS) |
| Logging | loguru JSON to stdout |
| Auth | JWT (access) + HttpOnly cookie (refresh), argon2 hashing |
