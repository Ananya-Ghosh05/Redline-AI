"""Request-ID middleware.

Generates a UUID4 request_id for every inbound HTTP request and:
  1. Stores it in structlog context-vars (appears in all log lines for the request)
  2. Echoes it back in the X-Request-ID response header
  3. Honours an upstream X-Request-ID header if already present (proxy pass-through)
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Honour upstream request-ID (load balancer / API gateway pass-through)
        request_id: str = (
            request.headers.get(_REQUEST_ID_HEADER) or uuid.uuid4().hex
        )

        # Bind to structlog context-vars so every log line in this request has it
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response: Response = await call_next(request)
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response
