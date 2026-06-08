# Auth Feature

The `auth` feature implements JWT-based authentication with Argon2 password
hashing and a PostgreSQL-backed session table for refresh tokens.

## Responsibilities

- Login: verify Argon2-hashed password → issue short-lived JWT access token + long-lived refresh token.
- JWT access tokens (HS256, 24h TTL) sent in `Authorization: Bearer` header, stored in-memory on frontend.
- Refresh tokens (opaque, SHA-256 hashed, 30-day sliding TTL) set as `HttpOnly Secure SameSite=Strict` cookie.
- Refresh rotation: each refresh issues a new token pair and deletes the old session row.
- Logout: revokes the current session, clears the cookie.
- Server-side session management in the `sessions` table (refresh token hash + expiry + metadata).
- Rate limiting on login: 10 requests per minute per IP (slowapi).
- Dependencies: `get_current_user` (JWT-based) and `requires_role(["admin"])` for route protection.
- Account management: password change, session listing, logout-everywhere, one-time reset-token flow.

## Reconciliation: JWT-over-Session-Store

The S0 auth skeleton reconciles the boilerplate's session-based auth with the design's locked JWT decision:

- **Access tokens (JWT)**: Short-lived (24h), stateless, not stored server-side. Verified via HMAC-SHA256.
- **Refresh tokens**: Opaque random strings stored as SHA-256 hashes in the `sessions` table.
- **Legacy code removed**: The original boilerplate's passlib-based password hashing, asyncpg-based session helpers, register endpoint, and password-reset endpoint were dead code and have been removed.

## Endpoints

All endpoints use the standard error envelope: `{"error_code": "...", "message": "...", "details": {}, "request_id": "..."}`.

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| POST | `/auth/login` | None | 10/min per IP | Authenticate with email+password, returns JWT + sets refresh cookie |
| POST | `/auth/logout` | Bearer JWT | None | Revoke current session, clear refresh cookie |
| POST | `/auth/refresh` | Cookie | None | Rotate refresh token, returns new JWT + sets new cookie |
| GET  | `/auth/me` | Bearer JWT | None | Return current user profile (with full_name) |
| POST | `/auth/change-password` | Bearer JWT | None | Change password (12-char min), revokes sibling sessions |
| GET  | `/auth/sessions` | Bearer JWT | None | List active sessions with user_agent, ip, last_used_at, is_current flag |
| POST | `/auth/logout-everywhere` | Bearer JWT | None | Revoke all sessions except current, clear refresh cookie |
| POST | `/api/v1/auth/reset-password` | None | None | Consume one-time reset token (email + token + new_password) |

## Service

Core auth functions in `service.py`:
- `verify_password(plain, hashed)` — Argon2 verification via `argon2-cffi`
- `issue_access_token(user_id)` — HS256 JWT with `sub`, `iat`, `exp` claims
- `verify_access_token(token)` — decode and validate JWT, return `user_id` or `None`
- `authenticate(db, email, password)` — lookup user + verify password
- `issue_tokens(db, user_id)` — create JWT + opaque refresh token, persist session
- `rotate_refresh(db, refresh_token)` — hash-lookup session, delete old, issue new pair
- `revoke_refresh(db, refresh_token)` — delete session row by token hash

Account management functions in `account_service.py`:
- `change_password(db, user_id, old, new)` — verify old, hash new, revoke sibling sessions
- `list_sessions(db, user_id, current_session_id)` — return list of `SessionInfo` DTOs
- `logout_everywhere(db, user_id, keep_current)` — delete all sessions except current
- `validate_password_strength(password)` — enforce 12-character minimum

## Repository

Data access in `repository.py`:
- `get_user_by_email(db, email)` — lookup non-deleted user
- `get_user_by_id(db, user_id)` — lookup non-deleted user
- `create_session(db, user_id, hash, expires_at)` — insert session row
- `get_session_by_hash(db, token_hash)` — lookup session by SHA-256 hash
- `delete_session_by_hash(db, token_hash)` — DELETE session by hash
- `list_active_sessions_for_user(db, user_id)` — active (non-expired) sessions, ordered by created_at DESC
- `delete_all_sessions(db, user_id, exclude_id)` — bulk DELETE, optionally preserving one session

## Models

### `User`
- Inherits `UUIDPrimaryKey`, `Timestamped`, `SoftDeletable`
- Fields: `email` (string, unique), `hashed_password` (text), `full_name` (nullable), `is_admin` (bool), `reset_token_hash` (nullable), `reset_token_expires_at` (nullable)
- Relationship: `sessions` (cascade all, delete-orphan)

### `Session`
- Inherits `UUIDPrimaryKey`, `Timestamped`
- Fields: `user_id` (FK → users.id CASCADE), `refresh_token_hash` (text), `expires_at` (timestamptz), `last_used_at` (nullable), `user_agent` (nullable), `ip` (nullable)
- Used for refresh-token storage and multi-session management

## Dependencies

- `get_current_user` — parses `Authorization: Bearer` header, verifies JWT, returns `User` ORM object. Raises 401 with `UNAUTHORIZED` error code.
- `requires_role(["admin"])` — wraps `get_current_user`, checks `user.is_admin`, raises 403 with `FORBIDDEN` if not admin.

## Password Reset CLI

```bash
uv run python scripts/reset_password.py <email>
```

Generates a one-time SHA-256-hashed token (1-hour TTL), stored in `users.reset_token_hash` and `users.reset_token_expires_at`. Prints the raw token to stdout. Consumed by `POST /api/v1/auth/reset-password`.

## Security

- Argon2 password hashing via `argon2-cffi`
- Rate limiting on `/auth/login`: 10 req/min/IP via slowapi
- Refresh tokens: SHA-256 hashed before storage (never stored in plaintext)
- Refresh cookie: `HttpOnly Secure SameSite=Strict`
- Access tokens: HMAC-SHA256, 24h TTL, in-memory only on frontend
- Password change revokes all sibling sessions (not the current one)
- Reset-password flow: one-time token, consumed on use (token hash + expiry cleared)

## Backlog / Future Enhancements

- Multi-user registration flow (`POST /auth/register` — schema ready, code removed pending reimplementation on JWT/argon2 stack).
- Email-based operations (verification, reset via email) deferred beyond v1.
