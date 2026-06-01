"""Tests for structured JSON logging via stdlib logging.

Verifies the JsonFormatter emits one JSON object per record with the
required fields: ts, level, event, request_id, service.
"""

import json
import logging

from app.features.core.observability.logging import (
    JsonFormatter,
    configure_logging,
    request_id_var,
)


def _last_record(capsys) -> dict:
    """Capture a single stdout JSON record and return as dict."""
    out = capsys.readouterr().out.strip()
    assert out, "expected at least one log line on stdout"
    lines = [ln for ln in out.splitlines() if ln.startswith("{")]
    assert lines, f"expected JSON log line, got: {out!r}"
    return json.loads(lines[-1])


def test_json_formatter_emits_required_fields() -> None:
    """JsonFormatter must include ts, level, event, request_id, service."""
    fmt = JsonFormatter(request_id_var)
    record = logging.LogRecord(
        name="mbi.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = fmt.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["event"] == "hello world"
    assert parsed["service"] == "mbi-backend"
    assert parsed["request_id"] == ""
    assert "ts" in parsed and parsed["ts"].endswith("Z")


def test_configure_logging_routes_root_to_json_stdout(capsys) -> None:
    """configure_logging() must install a JSON handler on the root logger."""
    configure_logging()
    logging.getLogger().info("boot-test")
    parsed = _last_record(capsys)
    assert parsed["event"] == "boot-test"
    assert parsed["level"] == "INFO"
    assert parsed["service"] == "mbi-backend"


def test_configure_logging_includes_request_id_from_contextvar(capsys) -> None:
    """Request_id set in ContextVar must appear in the JSON record."""
    configure_logging()
    token = request_id_var.set("req_abc123")
    try:
        logging.getLogger().info("scoped message")
        parsed = _last_record(capsys)
        assert parsed["request_id"] == "req_abc123"
        assert parsed["event"] == "scoped message"
    finally:
        request_id_var.reset(token)


def test_configure_logging_routes_uvicorn_through_root(capsys) -> None:
    """uvicorn.error logs must flow through the JSON formatter (not double-handled)."""
    configure_logging()
    logging.getLogger("uvicorn.error").info("uvicorn-test")
    parsed = _last_record(capsys)
    assert parsed["event"] == "uvicorn-test"
    assert parsed["service"] == "mbi-backend"
