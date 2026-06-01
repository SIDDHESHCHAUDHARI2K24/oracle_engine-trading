"""Small generic utilities used by the `core` feature."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime with timezone information."""
    return datetime.now(timezone.utc)

