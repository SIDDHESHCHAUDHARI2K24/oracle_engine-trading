"""Structured JSON logging for the MBI Oracle Engine backend.

Uses stdlib logging with a small JSON formatter. Required fields:
ts, level, event, request_id, service. UTF-8 encoded; safe on Windows.
"""

import json
import logging
import sys
import time
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def __init__(self, request_id_var: ContextVar[str]) -> None:
        super().__init__()
        self._request_id_var = request_id_var

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname,
                "event": record.getMessage(),
                "request_id": self._request_id_var.get() or "",
                "service": "mbi-backend",
            },
            ensure_ascii=False,
        )


def configure_logging() -> None:
    """Configure root logger with JSON formatter; route uvicorn through it."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(request_id_var))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
