# Auth Feature

The `auth` feature implements session-based authentication using
email + password credentials backed by PostgreSQL.

## Responsibilities

- User registration with unique email addresses.
- User login with bcrypt-hashed passwords.
- Session creation and storage in the `sessions` table.
- Session-based authentication via `session_id` cookie.
- Logout by invalidating the session and clearing the cookie.
- Direct password reset (no email flow) using email + new password.

## Files

- `models.py`  
  Defines SQL DDL strings for the `users` and `sessions` tables and
  exposes helper functions to create/read/update/delete users and
  sessions using `asyncpg.Connection` objects.

- `schemas.py`  
  Contains Pydantic models for request and response payloads:
  `RegisterRequest`, `LoginRequest`, `UserOut`, and `SessionOut`.

- `utils.py`  
  Provides:
  - Password hashing and verification using `passlib` (bcrypt).
  - Secure session token generation.
  - `get_current_user` dependency that resolves the current user
    from the `session_id` cookie and the `sessions` table.

- `routers.py`  
  Declares the `auth_router` with prefix `/auth` and wires the
  individual endpoint functions from the `endpoints/` package.

- `endpoints/`  
  - `register.py` – create a new user.
  - `login.py` – authenticate and create a session, setting the cookie.
  - `logout.py` – delete the session and clear the cookie.
  - `reset.py` – reset a password directly using email + new password.
  - `me.py` – return the currently authenticated user.

## Database Schema

The auth feature uses two tables in PostgreSQL:

- `users`  
  - `id` (serial primary key)  
  - `email` (unique)  
  - `password_hash`  
  - `created_at` (timestamp with time zone)

- `sessions`  
  - `id` (serial primary key)  
  - `user_id` (foreign key to `users.id`)  
  - `session_token` (unique)  
  - `created_at` (timestamp with time zone)  
  - `expires_at` (timestamp with time zone)

The helper `ensure_auth_schema()` in `models.py` can create these
tables on demand using `CREATE TABLE IF NOT EXISTS` statements.

## Backlog / Future Enhancements

- Email-based password reset using time-bound OTP codes sent to the
  user's registered email address when they initiate a reset from
  `endpoints/reset.py`. The user can change their password only after
  submitting the correct OTP. Each user may initiate at most three
  password reset flows per week to limit abuse, which may require
  additional helpers in `utils.py` and/or new fields in `models.py`
  to track OTPs and reset attempts.

- Reject password reset (and in-app password change, if added) when the
  new password is the same as the user's current password; require the
  new password to differ from the existing one.

- Send a \"Thank you for signing up\" email to the user's registered
  email address after successful registration via `endpoints/register.py`.

- Send a \"Thank you for using our services\" email to the user's
  registered email address when their account is deleted.

- Provide a dedicated account-deletion endpoint (for example,
  `endpoints/delete_account.py`) that deletes a user account only when
  the caller supplies the account email, the correct password, and a
  valid OTP. This will likely require helpers in `utils.py` and
  possibly new fields in `models.py` to track OTPs and deletion
  requests.

