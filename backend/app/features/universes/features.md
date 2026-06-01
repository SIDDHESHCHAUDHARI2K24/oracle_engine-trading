# Universes Feature

The `universes` feature manages named, versioned baskets of equity tickers
used as training and inference scopes by the ML pipeline.

## Responsibilities

- Store and serve named universes (e.g. S&P 500, Russell 1000, Russell 2000).
- Maintain a canonical ticker registry shared across universes.
- Track time-aware membership: when a ticker was added to a universe and,
  optionally, when it was removed.
- Expose read-only list and detail endpoints (auth-gated) for the frontend
  and downstream pipeline features to consume.
- Distinguish system-managed universes (seeded at startup, cannot be deleted
  or renamed by users) from user-created universes.

## Endpoints

All endpoints require a valid Bearer JWT (`Authorization: Bearer <token>`).

| Method | Path | Response | Description |
|--------|------|----------|-------------|
| GET | `/api/v1/universes` | `UniverseListResponse` | List all non-deleted universes ordered by name |
| GET | `/api/v1/universes/{id}` | `UniverseDetail` | Universe detail with active ticker list |

Error responses follow the standard envelope:
`{"error_code": "UNIVERSE_NOT_FOUND", "message": "...", "details": {}, "request_id": "..."}`.

## Files

- `models.py`
  SQLAlchemy 2.0 ORM models for `universes`, `tickers`, and
  `universe_memberships`. `Universe` inherits `UUIDPrimaryKey`,
  `Timestamped`, and `SoftDeletable` (has `deleted_at` column). `Ticker`
  inherits `UUIDPrimaryKey` and `Timestamped`.

- `schemas.py`
  Pydantic v2 response schemas (all use `ConfigDict(from_attributes=True)`):
  - `TickerSummary` — id, symbol, name, exchange, asset_type, active
  - `UniverseSummary` — id, name, display_name, is_system_managed, created_at
  - `UniverseDetail` — extends `UniverseSummary` with `tickers: list[TickerSummary]`
  - `UniverseListResponse` — `{universes: list[UniverseSummary], total: int}`

- `repository.py`
  Data access layer only. Three functions:
  - `list_universes(db)` — all non-deleted universes, ordered by name
  - `get_universe_by_id(db, id)` — single non-deleted universe, memberships + tickers eager-loaded
  - `list_active_tickers_for_universe(db, id)` — tickers where `removed_at IS NULL AND active = true`

- `service.py`
  Business logic. Calls repository, maps ORM objects to Pydantic schemas.
  - `list_universes(db)` → `UniverseListResponse`
  - `get_universe_detail(db, id)` → `UniverseDetail | None`

- `router.py`
  FastAPI `APIRouter` with prefix `/api/v1/universes`. Wires the two
  endpoints; raises `HTTP 404` with `UNIVERSE_NOT_FOUND` when service
  returns `None`.

## Database Schema

### `universes`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | `gen_random_uuid()` default |
| name | VARCHAR(100) | Unique, machine-readable slug |
| display_name | VARCHAR(255) | Human-readable label |
| is_system_managed | BOOLEAN | `false` default |
| created_at | TIMESTAMPTZ | Set on insert |
| updated_at | TIMESTAMPTZ | Updated on every write |
| deleted_at | TIMESTAMPTZ NULL | Soft-delete sentinel |

Unique constraint: `uq_universes_name` on `name`.

### `tickers`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| symbol | VARCHAR(20) | Unique exchange symbol (e.g. AAPL) |
| name | VARCHAR(255) | Company name |
| exchange | VARCHAR(50) NULL | Exchange code |
| asset_type | VARCHAR(20) | Default `'equity'` |
| active | BOOLEAN | Default `true` |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `universe_memberships`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| universe_id | UUID (FK → universes.id CASCADE) | |
| ticker_id | UUID (FK → tickers.id CASCADE) | |
| added_at | TIMESTAMPTZ | When ticker entered the universe |
| removed_at | TIMESTAMPTZ NULL | NULL = currently active member |

Unique constraint: `(universe_id, ticker_id, added_at)`.

Active membership query: `removed_at IS NULL`.
Point-in-time snapshot: `added_at <= date AND (removed_at IS NULL OR removed_at > date)`.

## Seeded System Universes

Three system-managed universes are defined (seeded by `scripts/seed_universes.py`):

| name | display_name | Seeded tickers |
|------|-------------|----------------|
| `sp500` | S&P 500 | ~503 (Wikipedia scrape) |
| `russell1000` | Russell 1000 | Not yet seeded |
| `russell2000` | Russell 2000 | Not yet seeded |

Only S&P 500 has its constituent tickers populated in v1.

## Current Limitations

- No write endpoints yet (add/remove ticker, create/delete universe). These
  are forthcoming in S1.
- No point-in-time snapshot query parameter (`?at=<date>`). Planned for S1.
- Soft-delete is modelled (`deleted_at` column exists) but no delete endpoint
  is exposed. The `WHERE deleted_at IS NULL` filter is already applied by the
  repository.
- Lazy ticker sync (validate against Alpaca) is deferred to S1.

## Running only the universes tests

```bash
cd backend
uv run python -m pytest app/features/universes/ -q
```
