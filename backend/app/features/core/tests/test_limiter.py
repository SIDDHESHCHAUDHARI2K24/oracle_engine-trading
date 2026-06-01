"""Tests that the rate limiter is correctly wired into the app."""

from fastapi.testclient import TestClient
from slowapi import Limiter

from app.app import create_app


def test_app_has_limiter_in_state() -> None:
    app = create_app()
    assert hasattr(app.state, "limiter")
    assert isinstance(app.state.limiter, Limiter)
