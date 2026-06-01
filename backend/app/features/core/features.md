# Core Feature

The `core` feature hosts **infrastructure concerns** that are shared across
all other features. It does **not** expose public HTTP endpoints; instead,
other features consume `core` via dependencies.

## Responsibilities

- Centralized configuration using environment variables and `.env` (`config.py`).
- Asynchronous PostgreSQL access using `asyncpg` (`database.py`).
- Shared Pydantic base schemas for API models (`base_model.py`).
- Reusable FastAPI dependencies for settings and database connections
  (`dependencies.py`).
- Small generic helpers such as UTC timestamp utilities (`utils.py`).
- Tests that validate configuration loading and basic database connectivity
  (`tests/`).

## Files

- `config.py`  
  Defines the `Settings` model using `pydantic-settings` and exposes a
  cached `settings` singleton. It reads `DATABASE_URL` and other values
  from the backend `.env` file and the environment.

- `database.py`  
  Implements `get_db()`, an async context manager that opens an
  `asyncpg` connection using `settings.database_url` and closes it when
  the context exits. This is meant to be wrapped as a FastAPI dependency.

- `base_model.py`  
  Contains `BaseSchema` (Pydantic base model configured with
  `from_attributes=True`) and `TimestampedSchema`, which adds
  `created_at` and `updated_at` fields for models that need timestamps.

- `dependencies.py`  
  Provides dependency helpers:
  - `get_settings_dep()` and `SettingsDep` for injecting `Settings`.
  - `get_db_dep()` and `DbDep` for injecting a database connection that
    uses `get_db()` under the hood.

- `utils.py`  
  Currently exposes `utc_now()` for retrieving the current UTC datetime.
  Additional small, generic helpers for the backend can live here.

- `tests/`  
  - `test_core_config.py` ensures that `DATABASE_URL` is loaded correctly
    into `settings`.
  - `test_database_connection.py` verifies that a simple `SELECT 1`
    query succeeds against the configured PostgreSQL instance.

## How other features use `core`

Features such as `auth` should import dependencies from `core` rather
than re-implementing configuration or database access. Typical patterns:

- Use `SettingsDep` to access configuration within route handlers.
- Use `DbDep` to obtain an `asyncpg.Connection` for executing queries.

## Running only the `core` tests

From the `backend/` directory:

```bash
uv run python -m pytest app/features/core/tests -q
```

