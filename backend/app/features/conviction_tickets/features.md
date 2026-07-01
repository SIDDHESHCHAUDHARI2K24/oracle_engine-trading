# Conviction Tickets — Feature Documentation

## Overview

Block A8 — Pipeline A's user-facing output. Transforms daily predictions into
filtered, tradable conviction tickets with lifecycle management and outcome tracking.

Each ticket represents a standalone (ticker, horizon) investment thesis backed by:
1. A positive predicted return above a calibrated conformal bound
2. At least 2 of 4 backtest strategies passing
3. A conviction score from the ensemble model

## Architecture

```
Daily Inference Flow
    │
    ├── inference → predictions
    │
    └── Filter Gate (4 locked criteria)
         │
         ├── PASS → TicketService.emit_tickets()
         │           │
         │           ├── Calendar-correct resolution date
         │           ├── upsert_tickets (idempotent)
         │           └── create_filter_run (audit trail)
         │
         └── FAIL → FilterRun only (audit, zero emitted)

Resolution Flow (weekdays 5pm ET)
    │
    └── resolve_tickets()
         ├── get_close(base_date), get_close(resolution_date)
         ├── actual_return = resolution_close / base_close - 1
         ├── outcome: win / loss / flat
         └── status: TRADABLE→EXPIRED, REVIEWED/ACTIONED→RESOLVED
```

### Key Files

| File | Purpose |
|---|---|
| `models.py` | `ConvictionTicket` + `FilterRun` ORM models |
| `service.py` | `TicketService.emit_tickets()` — filter → calendar → upsert |
| `filter/gate.py` | 4-criteria filter gate (pure functions, no DB) |
| `resolution/service.py` | `resolve_tickets()` — outcome computation |
| `repository.py` | Upsert, inbox, history, resolution query, status update |
| `schemas.py` | Pydantic v2 request/response schemas |
| `router.py` | FastAPI router at `/api/v1/tickets` |
| `endpoints/tickets.py` | Inbox + history endpoints |
| `endpoints/lifecycle.py` | Status transition endpoints + validation |

### ORM Models

**ConvictionTicket**:
- Inferred columns: `inference_run_id`, `ticker_id`, `universe_id`, `inference_date`
- Horizon: `horizon` (T1/T5/T10/T15), `direction` (LONG)
- Numerical: `predicted_return`, `conviction_score`, `conformal_lower/upper/alpha`
- Backtest: `backtest_run_id`, `backtest_passes`, `backtest_pass_strategies`
- Lifecycle: `status`, `resolution_date`, `actual_return`, `outcome`
- Metadata: `created_by_user_id`, `user_notes`
- Unique constraint: `(inference_run_id, ticker_id, horizon)` — one ticket per prediction

**FilterRun**:
- `inference_run_id`, `backtest_run_id`
- `num_predictions_evaluated`, `num_tickets_emitted`
- `filter_config` (JSONB — holds W_max map)
- Audit trail for every filter gate execution

## The Filter Gate (4 Locked Criteria)

All 4 criteria must pass (Boolean AND):

1. **conviction_score > 67** (strict, not >=) — `_check_conviction()`
2. **predicted_return > 0** (long-only) — `_check_direction()`
3. **backtest_passes >= 2 of 4 strategies** — `_check_backtest()`
4. **conformal_width < W_max** (per-horizon) — `_check_width()`

`W_max` is the per-universe 90th percentile conformal width from the calibration
set, stored on the conformal artifact's `model_metadata` at train time (P5.T0).
In production, read from the artifact store. In tests, passed explicitly.

**Rationale**: Each criterion gates a different failure mode:
- Conviction: noise filtering (the model must be confident)
- Direction: long-only constraint (no short signals in v1)
- Backtest: empirical validation (the ticker's strategy suite must backtest well)
- Width: calibration quality (predictions with excessive uncertainty are filtered)

**File**: `filter/gate.py:26`

## Ticket Lifecycle

```
TRADABLE ──(no action by resolution_date)──► EXPIRED
    │
    │ POST /tickets/{id}/review
    ▼
REVIEWED ──POST /tickets/{id}/action──► ACTIONED ──resolve_tickets()──► RESOLVED
```

### Valid Transitions

| From | To |
|---|---|
| TRADABLE | REVIEWED, ACTIONED |
| REVIEWED | ACTIONED |
| ACTIONED | (terminal) |
| RESOLVED | (terminal) |
| EXPIRED | (terminal) |

Invalid transitions are rejected with `INVALID_TRANSITION` error code.
The state machine is enforced in `endpoints/lifecycle.py:17`.

### Resolution vs Expiry

- **EXPIRED**: a TRADABLE ticket whose `resolution_date` passed without human
  action. Outcome is still computed for tracking.
- **RESOLVED**: a REVIEWED or ACTIONED ticket whose outcome has been computed.

## Correctness Contract for Outcome Resolution

```
actual_return = close_at_resolution / close_at_base - 1
```

**The correctness crux**: `actual_return` is computed as `resolution_close / base_close - 1`,
where:
- `base_close` = OHLCV close on `inference_date` (the bar we predicted from)
- `resolution_close` = OHLCV close on `resolution_date` (the bar we predicted to)

This is a **simple holding return** — not annualized, not excess, not log.
It represents exactly the percentage change an investor would realize holding
from inference_date to resolution_date.

### Outcome Classification

- **win**: `actual_return > 0`
- **loss**: `actual_return < 0`
- **flat**: `|actual_return| < 0.001` (within 10bp — essentially unchanged)

### Edge Cases

| Case | Behavior |
|---|---|
| Missing base bar | Deferred (not errored) |
| Missing resolution bar | Deferred (not errored) |
| Non-trading resolution date | Roll to next trading session (up to 7 days) |
| No trading sessions found | Deferred |
| Any exception per ticket | Skips that ticket, increments error counter |
| TRADABLE at resolution | Status → EXPIRED (still computes outcome) |
| REVIEWED/ACTIONED at resolution | Status → RESOLVED |
| Already resolved/expired | Skipped (`get_tickets_for_resolution` filters by status) |

### Idempotency

- **Resolution**: re-running `resolve_tickets` does not double-resolve tickets.
  Once resolved/expired, status is excluded from `get_tickets_for_resolution()`.
- **Emission**: `upsert_tickets` uses `ON CONFLICT DO NOTHING` on
  `(inference_run_id, ticker_id, horizon)` — re-running the same prediction
  batch produces zero new rows.

## Multi-Horizon Independence

Each `(ticker, horizon)` pair is evaluated independently:
- One ticker can produce up to **4 tickets** (T1, T5, T10, T15)
- Each has its own `W_max` threshold
- Each has its own calendar-correct `resolution_date`
- Outcome resolution is per-ticket, not aggregated

## Resolution Date Calculation

Calendar-correct using NYSE sessions:
- `resolution_date = trading_days(inference_date, +90d)[horizon_sessions_index]`
- T1 → sessions[1], T5 → sessions[5], T10 → sessions[10], T15 → sessions[15]
- Falls back to `inference_date` if insufficient sessions (edge case, not errored)
- **File**: `service.py:53-61`

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/tickets` | any | Inbox — TRADABLE tickets sorted by conviction DESC |
| GET | `/api/v1/tickets/{id}` | any | Single ticket detail |
| GET | `/api/v1/tickets/history` | any | Chronological with status/outcome filters |
| POST | `/api/v1/tickets/{id}/review` | admin | Mark reviewed |
| POST | `/api/v1/tickets/{id}/action` | admin | Mark actioned (with notes) |

### Filtering (Inbox + History)

- Inbox: filter by `universe_id`, default sort `conviction_score DESC`, limit 100
- History: filter by `universe_id`, `outcome`, default sort `inference_date DESC`

## Orchestration

### Daily Flow (filter + emit)
- Wired into `daily_inference` Prefect flow after inference completes per universe
- Predictions → filter gate → calendar resolution dates → upsert tickets
- Filter reads the **freshest persisted** `backtest_metrics` (does not wait on a run)
- **File**: `app/orchestration/flows/daily_inference.py:78`

### Weekly Backtest (independent)
- Runs 4am ET Sundays via `weekly_backtest` flow, before model retrain
- Backfill backtest results → filter reads latest on next daily run

### Outcome Resolution
- `outcome_resolution` Prefect flow: weekdays 5:00pm ET
- Queries all tickets with `resolution_date <= today` and unresolved status
- Computes `actual_return` and `outcome` from OHLCV bars
- **File**: `app/orchestration/flows/outcome_resolution.py`

## Output Contract (for Pipeline B)

Each `ConvictionTicket` is a **standalone signal** ready for consumption:

- **(ticker, horizon)** uniquely identifies the trade thesis
- **conviction_score**: model confidence gauge
- **conformal_lower/upper**: calibrated uncertainty interval
- **backtest_passes + pass_strategies**: empirical validation detail
- **resolution_date**: when to evaluate the trade
- **actual_return + outcome**: ground truth for reinforcement learning

Direction enum supports `SHORT` (reserved for v2 when short signals are
permitted).

## Locked Decisions

- **4-criteria filter gate**: conviction, direction, backtest, conformal width.
  All must pass. No relaxing individual criteria without a spec deviation.
- **Long-only**: `_check_direction()` requires `predicted_return > 0`. No short
  tickets in v1. `direction` column defaults to `LONG`.
- **Per-horizon W_max**: conformal width threshold is horizon-specific, read
  from the calibration artifact's model_metadata.
- **Calendar-correct resolution**: resolution dates are NYSE sessions, not
  calendar days. Non-trading resolution dates roll forward.
- **DB-level idempotency**: `ON CONFLICT DO NOTHING` on the natural key
  `(inference_run_id, ticker_id, horizon)`.
- **Resolution correctness contract**: `actual_return = resolution_close / base_close - 1`.
  This is the locked formula. Any change requires a spec deviation and migration
  of historical outcomes.
