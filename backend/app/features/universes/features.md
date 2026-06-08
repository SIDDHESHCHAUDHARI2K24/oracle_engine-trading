# Universes Feature

The `universes` feature manages named, versioned baskets of equity tickers
used as training and inference scopes by the ML pipeline.

## Responsibilities

- Store and serve named universes (e.g. S&P 500, Russell 1000, Russell 2000).
- Maintain a canonical ticker registry shared across universes, lazily
  validated against Alpaca's asset master.
- Track time-aware membership: when a ticker was added to a universe and,
  optionally, when it was removed.
- Expose full CRUD + membership management + CSV import endpoints (admin-gated for writes).
- Distinguish system-managed universes (seeded at startup, cannot be deleted
  or renamed) from user-created universes.
- Seed three system-managed universes via `scripts/seed_universes.py` with
  idempotent reconciliation of constituents.

## Endpoints

All endpoints require a valid Bearer JWT. Write endpoints additionally require admin role.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/universes` | Bearer | List universes; `?include_deleted=true` to include soft-deleted; includes ticker count |
| GET | `/api/v1/universes/{id}` | Bearer | Universe detail with active ticker list |
| POST | `/api/v1/universes` | Admin | Create a new universe (name, display_name, description) |
| PATCH | `/api/v1/universes/{id}` | Admin | Update a non-system-managed universe |
| DELETE | `/api/v1/universes/{id}` | Admin | Soft-delete (sets `deleted_at`); blocked for system-managed |
| GET | `/api/v1/universes/{id}/membership` | Admin | List members; optional `?at=<date>` for point-in-time snapshot |
| POST | `/api/v1/universes/{id}/membership` | Admin | Add tickers by symbol list; returns `AddResult` |
| DELETE | `/api/v1/universes/{id}/membership/{ticker_id}` | Admin | Remove a ticker (sets `removed_at`) |
| POST | `/api/v1/universes/{id}/membership/import` | Admin | CSV upload (multipart); 5 MB / 50k row caps; per-row parse errors |

Error codes: `UNIVERSE_NOT_FOUND`, `DUPLICATE_UNIVERSE_NAME`, `SYSTEM_MANAGED_UNIVERSE`,
`MEMBERSHIP_NOT_FOUND`, `FILE_TOO_LARGE`, `EMPTY_FILE`.

## Ticker Registry

- `shared/alpaca_assets.py` — fetches Alpaca asset list on app startup, builds a
  `{symbol: Asset}` lookup map for lazy validation.
- `normalize_symbol(raw)` — normalizes dots→dashes, uppercase. Ensures
  canonical symbol format before Alpaca lookup or DB insert.
- `validate_and_upsert_tickers(db, symbols, alpaca_map)` — validates each
  symbol against the provided asset map, upserts valid ones into the `tickers`
  table, returns `UpsertResult(inserted, skipped, invalid)`.

## Universe CRUD

- **Create** (`create_universe`): validates unique name, generates `public_id` (`uni_XXXXXXXXXX`), creates
  with `is_system_managed=False`.
- **Update** (`update_universe`): patch name/display_name/description. Blocks system-managed universes
  (`SystemManagedUniverseError` → 403).
- **Soft-delete** (`soft_delete_universe`): sets `deleted_at` to now. Blocks system-managed.
- **Restore** (`restore_universe`): clears `deleted_at`. Queries include_deleted=True to find the entity.

## Membership

- `UniverseMembership` is time-aware: `added_at` (when ticker entered) + `removed_at` (NULL = active).
- Unique constraint on `(universe_id, ticker_id, added_at)` — same ticker can re-enter after removal.
- `add_members(db, universe_id, symbols)` — validates against Alpaca, creates tickers if needed,
  returns `AddResult(added, already_present, invalid)`.
- `remove_member(db, universe_id, ticker_id)` — sets `removed_at` to now, preserves history.
- `get_members(db, universe_id, at_date)` — point-in-time snapshot via `added_at <= date
  AND (removed_at IS NULL OR removed_at > date)`.

## CSV Import

- Multipart upload via `POST /{id}/membership/import`
- `MAX_FILE_SIZE = 5 MB`, `MAX_ROWS = 50000`
- Reads CSV with `utf-8-sig` encoding. Skips header row if first cell is `symbol`/`ticker`/`code`.
- Per-row parse errors collected (non-fatal), returned in `ImportResult.parse_errors`.
- Empty file → 400 `EMPTY_FILE`.

## Constituent Sources

Swappable adapters under `shared/constituents/adapters/`:

| Adapter | Source | Method |
|---------|--------|--------|
| `sp500.py` | Wikipedia (`List of S&P 500 companies`) | HTML table scrape |
| `russell1000.py` | iShares IWB holdings CSV | HTTP GET + CSV parse |
| `russell2000.py` | iShares IWM holdings CSV | HTTP GET + CSV parse |

Each implements the `ConstituentSource` base class (`fetch_constituents() -> list[str]`).

## Seed Script

```bash
cd backend
uv run python scripts/seed_universes.py
```

Idempotent — re-running reconciles memberships (adds new constituents, valid via Alpaca).
Output per index: "Fetched N constituents", "Added/Already present/Invalid" breakdown.

## Schemas

- `TickerSummary` — id, symbol, name, exchange, asset_type, active
- `UniverseSummary` — id, name, display_name, description, public_id, last_retrain_at, is_system_managed, created_at, ticker_count
- `UniverseDetail` — extends `UniverseSummary` with `tickers: list[TickerSummary]`
- `UniverseListResponse` — `{universes: list[UniverseSummary], total: int}`
- `UniverseCreate` — name, display_name, description (nullable)
- `UniverseUpdate` — all fields optional
- `AddMembersRequest` — `symbols: list[str]`
- `AddResult` — added, already_present, invalid

## Files

- `models.py` — SQLAlchemy ORM: `Universe` (soft-deletable, system_managed flag, public_id), `Ticker` (symbol unique, active flag), `UniverseMembership` (added_at/removed_at, time-aware)
- `schemas.py` — Pydantic v2 request/response DTOs
- `repository.py` — Data access: list/get/create universe, upsert tickers, add/remove/list memberships, point-in-time queries
- `service.py` — Business logic: CRUD, membership management with Alpaca validation, system-managed protection, public_id generation
- `router.py` — FastAPI `APIRouter(prefix="/api/v1/universes")`, wires list/detail + includes membership + import sub-routers
- `shared/alpaca_assets.py` — Alpaca asset map builder and symbol normalization
- `shared/constituents/` — `ConstituentSource` base + three adapters for S&P 500, Russell 1000/2000

## Database Schema

### `universes`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | VARCHAR(100) | Unique, machine-readable slug |
| display_name | VARCHAR(255) | Human-readable label |
| description | TEXT NULL | |
| is_system_managed | BOOLEAN | Default false |
| public_id | VARCHAR(20) NULL | Human-readable ID (e.g. `uni_xxxxxxxxxx`) |
| last_retrain_at | TIMESTAMPTZ NULL | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |
| deleted_at | TIMESTAMPTZ NULL | Soft-delete sentinel |

### `tickers`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| symbol | VARCHAR(20) | Unique exchange symbol (e.g. AAPL) |
| name | VARCHAR(255) | Company name |
| exchange | VARCHAR(50) NULL | Exchange code |
| asset_type | VARCHAR(20) | Default `'equity'` |
| active | BOOLEAN | Default true |
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

## Running only the universes tests

```bash
cd backend
uv run python -m pytest app/features/universes/ -q
```
