"""Tests that the rate limiter is correctly wired into the app."""

from fastapi.testclient import TestClient
from slowapi import Limiter

from app.app import create_app


def test_app_has_limiter_in_state() -> None:
    app = create_app()
    assert hasattr(app.state, "limiter")
    assert isinstance(app.state.limiter, Limiter)


def test_rate_limit_429_uses_standard_error_envelope() -> None:
    """Rate limit response uses standard {error_code, message, details} envelope."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    # Exhaust the 10/min limit
    for _ in range(10):
        client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "wrong"})

    resp = client.post(
        "/api/v1/auth/login", json={"email": "x@example.com", "password": "wrong"}
    )
    assert resp.status_code == 429
    data = resp.json()
    assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "message" in data
    assert "details" in data
