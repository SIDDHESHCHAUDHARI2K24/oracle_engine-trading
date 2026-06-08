"""FastAPI dependency helpers for the `core` feature.

Re-exports reusable dependency callables and aliases for injecting
configuration and database sessions into route handlers.
"""

from fastapi import Depends

from app.features.core.config import Settings, get_settings
from app.features.core.database import get_async_session
from app.features.core.observability.logging import request_id_var


def get_settings_dep() -> Settings:
    """Return the global `Settings` instance as a dependency."""
    return get_settings()


def get_request_id() -> str:
    return request_id_var.get() or ""


SettingsDep = Depends(get_settings_dep)
DbDep = Depends(get_async_session)
