"""Request-ID middleware for the MBI Oracle Engine backend.

Assigns a unique request_id per HTTP request, stores it in the
stdlib logging context, and includes it in the response headers.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.features.core.observability.logging import request_id_var


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a unique request_id per request and bind it to the logging context."""

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        request_id = (
            request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        )
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)
