# Manual Password Reset Runbook

Pipeline A v1 uses a single hardcoded admin user. Password reset is a manual CLI operation.

---

## Prerequisites

- Access to the machine running the backend
- `.env` file with `DATABASE_URL` configured
- The `uv` package manager installed

---

## Step 1: Generate a One-Time Reset Token

```bash
cd backend
uv run python scripts/reset_password.py admin@mbilabs.io
```

This outputs a one-time token to stdout, valid for **1 hour**.

Example output:
```
aB3xK7mP2qR9vL5wN8dF1jH4oU6sY0cG
```

The script:
1. Generates a cryptographically random 32-byte token
2. Stores its SHA-256 hash in `users.reset_token_hash` with a 1-hour expiry
3. Prints the raw token (the hash cannot be reversed, so save the printed value)

---

## Step 2: Use the Token to Set a New Password

```bash
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"token": "aB3xK7mP2qR9vL5wN8dF1jH4oU6sY0cG", "new_password": "your-new-secure-password"}'
```

The password requirements:
- Minimum 8 characters
- Recommend: 12+ characters, mix of case, digits, and symbols

---

## Step 3: Verify the New Password Works

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@mbilabs.io", "password": "your-new-secure-password"}'
```

Expected response: 200 with a JWT access token.

---

## Security Notes

- The reset token is **single-use**. After a successful password change, the token hash is cleared.
- Tokens expire after **1 hour**. If expired, re-run Step 1 for a fresh token.
- The raw token is printed to stdout only. Do not share it, log it, or commit it.
- If the admin email differs from `admin@mbilabs.io`, pass the correct email to the script:
  ```bash
  uv run python scripts/reset_password.py your-actual-admin@email.com
  ```

---

## If the Script Can't Find the User

```
No active user found with email: admin@mbilabs.io
```

This means the user doesn't exist or has `deleted_at` set. To create the admin user:

```bash
cd backend
uv run python scripts/seed_admin.py
```

This creates the default admin user with the password from `ADMIN_PASSWORD` in `.env` (or the
script's default). Then run the reset flow above to set a known password.

---

## If the Reset Endpoint Doesn't Exist

The `/api/v1/auth/reset-password` endpoint must be implemented. Check:

1. `backend/app/features/auth/router.py` — the endpoint should be registered
2. `backend/app/features/auth/schemas.py` — a `PasswordResetRequest` schema should exist
3. If missing, implement or reset the password directly in the database:

```bash
# Direct DB reset (fallback only — bypasses token flow)
psql -U mbi_user -d mbi -p 5433 -c "
UPDATE users
SET password_hash = crypt('new-password', gen_salt('bf'))
WHERE email = 'admin@mbilabs.io';
"
```

**Note**: The direct DB approach above assumes `pgcrypto` is available. With the actual
`argon2-cffi` hashing, use the Python script instead.
