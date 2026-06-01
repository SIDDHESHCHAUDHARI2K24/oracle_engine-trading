"""Shared slowapi rate limiter instance and custom exception handler.

Import this module wherever rate limiting is needed:
  - app.py: wire into app.state and exception handler
  - auth/endpoints/login.py: apply @limiter.limit("10/minute")
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return rate limit errors using the project's standard error envelope."""
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
            "details": {"limit": str(exc.limit)},
            "request_id": request.state.request_id
            if hasattr(request.state, "request_id")
            else None,
        },
    )
