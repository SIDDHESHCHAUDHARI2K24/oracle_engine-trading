# Core Feature

The `core` feature provides cross-cutting infrastructure shared by all other features.

## Responsibilities

- Application configuration via pydantic-settings (`.env`, typed settings singleton).
- Async PostgreSQL + TimescaleDB database access: SQLAlchemy 2.0 async engine, session factory, per-request session dependency.
- Shared SQLAlchemy ORM base class and column mixins (UUID PK, timestamps, soft-delete).
- Structured JSON logging with request-ID correlation.
- HTTP request-ID middleware (generates `X-Request-ID`, passes to logging context).
- Rate limiting infrastructure (slowapi integration, standard 429 error envelope).
- Pydantic v2 base schemas (from_attributes for ORM mapping).

## Files

- `config.py` — `Settings(BaseSettings)` loaded from `.env`. Fields: `database_url`, `jwt_secret`, `jwt_access_ttl_minutes`, `jwt_refresh_ttl_days`, `admin_email`, `admin_password`, `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `artifact_store_path`, `cors_allow_origins`, `log_level`, `project_name`, `environment`. Validates `DATABASE_URL` starts with `postgresql+asyncpg://`. Exported as a singleton via `get_settings()`.

- `database.py` — Async SQLAlchemy engine (asyncpg driver, pool_size=10, max_overflow=10, statement_timeout=30s), `async_session_factory` (async_sessionmaker), and `get_async_session` FastAPI dependency (yields and closes per-request).

- `base.py` — `Base` (DeclarativeBase), `UUIDPrimaryKey` (UUID PK + `gen_random_uuid()` server default), `Timestamped` (created_at + updated_at), `SoftDeletable` (deleted_at TIMESTAMPTZ NULL). All feature models inherit from these.

- `base_model.py` — `BaseSchema(BaseModel, from_attributes=True)`, `TimestampedSchema` (created_at + updated_at). Base for all Pydantic response schemas.

- `dependencies.py` — Type aliases: `SettingsDep` (Annotated settings), `DbDep` (Annotated AsyncSession).

- `limiter.py` — slowapi `Limiter` with `get_remote_address` key function. Custom 429 handler returning standard error envelope: `{"error_code": "RATE_LIMIT_EXCEEDED", "message": "...", "details": {"limit": "..."}, "request_id": "..."}`.

- `utils.py` — `utc_now()` helper returning timezone-aware UTC datetime.

- `routers.py` — Placeholder (no routes; core is infrastructure-only).

- `observability/logging.py` — stdlib `logging` with custom `JsonFormatter`. Required fields per record: `ts`, `level`, `event`, `request_id`, `service`. Uses `ContextVar` (`request_id_var`) for async-safe correlation. Uvicorn integration: clears uvicorn handlers, sets `propagate=True` so access logs route through JSON formatter.

- `observability/middleware.py` — `RequestIdMiddleware` (Starlette BaseHTTPMiddleware). Generates `req_<12-hex>` ID or reuses incoming `X-Request-ID` header. Sets the `request_id_var` context var and includes `X-Request-ID` in responses.

## Design Decisions

- **Stdlib logging over loguru**: Despite the design doc specifying loguru, the implementation uses stdlib logging with a custom JSON formatter. This avoids an extra dependency and integrates more cleanly with uvicorn's existing handler infrastructure. The JSON output contract (fields: `ts`, `level`, `event`, `request_id`, `service`) is preserved.
- **Application factory pattern**: `create_app()` in `app.py` assembles middleware (CORS, request-ID), rate-limiter, health/ready routes, and feature routers. Standard FastAPI 12-factor pattern.
- **No asyncpg raw connections**: Unlike the boilerplate which used raw `asyncpg.Connection` dependencies, all DB access goes through SQLAlchemy 2.0 `AsyncSession` with ORM models.
