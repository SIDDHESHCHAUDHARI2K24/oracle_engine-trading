"""Integration tests for JWT auth endpoints.

These tests exercise the actual HTTP layer via TestClient using the seeded
admin user (admin@mbilabs.io / change-me-on-first-login).

Pre-conditions:
  - DATABASE_URL and JWT_SECRET env vars are set.
  - Admin user is seeded (run: uv run python scripts/seed_admin.py).
  - In CI these are guaranteed by the workflow before pytest runs.
"""

from fastapi.testclient import TestClient

from app.app import create_app

ADMIN_EMAIL = "admin@mbilabs.io"
ADMIN_PASSWORD = "change-me-on-first-login"

# Module-scoped client — app + settings are created once.
_client = TestClient(create_app())


def test_login_valid_credentials_returns_token() -> None:
    resp = _client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == ADMIN_EMAIL


def test_login_sets_refresh_cookie() -> None:
    resp = _client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies


def test_login_wrong_password_returns_401() -> None:
    resp = _client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email_returns_401() -> None:
    resp = _client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "any"}
    )
    assert resp.status_code == 401


def test_me_with_valid_bearer_token_returns_user() -> None:
    login = _client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]
    resp = _client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == ADMIN_EMAIL
    assert resp.json()["is_admin"] is True


def test_me_without_token_returns_401() -> None:
    resp = _client.get("/auth/me")
    assert resp.status_code == 401


def test_logout_with_valid_token_returns_ok() -> None:
    login = _client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    token = login.json()["access_token"]
    resp = _client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
