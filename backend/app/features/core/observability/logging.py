"""Structured logging configuration for the MBI Oracle Engine backend.

Configures loguru to emit JSON-formatted logs to stdout with the
required fields: ts, level, request_id, event. Never logs secrets.
"""

import io
import logging
import sys
from contextvars import ContextVar

from loguru import logger

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class InterceptHandler(logging.Handler):
    """Forward standard library logs to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        level = logger.level(record.levelname).name if record.levelname else "INFO"

        frame = logging.currentframe()
        depth = 0
        while frame and hasattr(frame, "f_code"):
            depth += 1
            frame = frame.f_back
            if depth > 20:
                break

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _patcher(record: dict) -> None:
    """Attach request_id and service name to every log record."""
    record["extra"]["service"] = "mbi-backend"
    record["extra"]["request_id"] = request_id_var.get() or ""


def _wrap_stdout() -> None:
    """Re-wrap stdout as UTF-8 so loguru JSON doesn't fail on Windows cp1252."""
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def configure_logging() -> None:
    """Configure loguru with structured JSON output and uvicorn interception."""
    _wrap_stdout()
    logger.remove()

    logger.configure(patcher=_patcher)

    logger.add(
        sys.stdout,
        serialize=True,
        level="INFO",
        format="",
        backtrace=False,
        catch=True,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for _logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        _logger = logging.getLogger(_logger_name)
        _logger.handlers = []
        _logger.propagate = False

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addHandler(InterceptHandler())
