"""Tests for core configuration loading."""

from app.features.core.config import settings


def test_database_url_is_loaded() -> None:
    """DATABASE_URL should be present and non-empty."""
    assert isinstance(settings.database_url, str)
    assert settings.database_url != ""

