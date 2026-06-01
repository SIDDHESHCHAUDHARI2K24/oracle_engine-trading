# Auth Feature

The `auth` feature implements JWT-based authentication with an argon2-hashed
password store and a PostgreSQL-backed session table for refresh tokens.

## Responsibilities

- Admin user seeding via `scripts/seed_admin.py` (single-user v1; multi-user schema ready).
- Login: verify argon2-hashed password → issue short-lived JWT access token + long-lived refresh token.
- JWT access tokens (HS256, 24h TTL) sent in `Authorization: Bearer` header, stored in-memory on frontend.
- Refresh tokens (opaque, SHA-256 hashed, 30-day sliding TTL) set as `HttpOnly Secure SameSite=Strict` cookie.
- Refresh rotation: each refresh issues a new token pair and deletes the old session row.
- Logout: revokes the current session, clears the cookie.
- Server-side session management in the `sessions` table (refresh token hash + expiry + metadata).
- Rate limiting on login: 10 requests per minute per IP (slowapi).
- Dependencies: `get_current_user` (JWT-based) and `requires_role(["admin"])` for route protection.

## Reconciliation: JWT-over-Session-Store

The S0 auth skeleton reconciles the boilerplate's session-based auth with the design's locked JWT decision:

- **Access tokens (JWT)**: Short-lived (24h), stateless, not stored server-side. Verified via HMAC-SHA256.
- **Refresh tokens**: Opaque random strings stored as argon2 hashes in the `sessions` table. The `sessions` table IS the refresh-token store — an extension of the boilerplate's session pattern, not a replacement.
- **Legacy code removed**: The original boilerplate's passlib-based password hashing, asyncpg-based session helpers, register endpoint, and password-reset endpoint were dead code (not wired into routers, referenced functions that didn't exist on ORM models) and have been removed. See commit history for the original boilerplate sources.

## Endpoints

All endpoints use the standard error envelope: `{"error_code": "...", "message": "...", "details": {}, "request_id": "..."}`.

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/auth/login` | None | 10/min per IP | Authenticate with email+password, returns JWT + sets refresh cookie |
| POST | `/auth/logout` | Bearer JWT | None | Revoke current session, clear refresh cookie |
| POST | `/auth/refresh` | Cookie | None | Rotate refresh token, returns new JWT + sets new cookie |
| GET  | `/auth/me` | Bearer JWT | None | Return current user profile |

## Files

- `models.py` — SQLAlchemy ORM: `User` (UUID PK, email, hashed_password, full_name, is_admin, soft-deletable) and `Session` (UUID PK, user_id FK, refresh_token_hash, expires_at, last_used_at, user_agent, ip, timestamped).
- `schemas.py` — Pydantic v2: `LoginRequest`, `TokenResponse`, `UserResponse`, `SessionInfo`.
- `repository.py` — Data access: `get_user_by_email`, `get_user_by_id`, `create_session`, `get_session_by_hash`, `delete_session_by_hash`, `delete_all_sessions`.
- `service.py` — Business logic: `verify_password` (argon2), `issue_access_token`, `verify_access_token`, `authenticate`, `issue_tokens`, `rotate_refresh`, `revoke_refresh`.
- `dependencies.py` — FastAPI deps: `get_current_user` (parses Bearer token, verifies JWT), `requires_role(["admin"])`.
- `routers.py` — APIRouter with prefix `/auth`, wires login/logout/refresh/me endpoints.
- `endpoints/login.py` — Rate-limited login handler.
- `endpoints/logout.py` — Session revocation.
- `endpoints/me.py` — Current user profile.
- `endpoints/refresh.py` — Token rotation.

## Database Schema

### `users`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | `gen_random_uuid()` default |
| email | VARCHAR(255) | Unique, not null |
| hashed_password | TEXT | Argon2 hash |
| full_name | VARCHAR(255) | Nullable |
| is_admin | BOOLEAN | Default false |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |
| deleted_at | TIMESTAMPTZ NULL | Soft-delete sentinel |

Unique constraint: `uq_users_email` on `email`.

### `sessions`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | `gen_random_uuid()` default |
| user_id | UUID (FK → users.id CASCADE) | |
| refresh_token_hash | TEXT | SHA-256 of opaque token |
| expires_at | TIMESTAMPTZ | Sliding 30-day expiry |
| last_used_at | TIMESTAMPTZ NULL | Updated on each refresh |
| user_agent | TEXT NULL | Client user-agent string |
| ip | VARCHAR(50) NULL | Client IP address |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

## Backlog / Future Enhancements

- Multi-user registration flow (`POST /auth/register` — schema ready, code removed pending reimplementation on JWT/argon2 stack).
- Password change from `/settings/account` (`POST /api/v1/auth/change-password` — planned S1).
- Session listing + log-out-everywhere (`GET /api/v1/auth/sessions`, `POST /api/v1/auth/logout-everywhere` — planned S1).
- Password-reset CLI (`scripts/reset_password.py` with one-time token — planned S1).
- Email-based operations (verification, reset via email) deferred beyond v1.
