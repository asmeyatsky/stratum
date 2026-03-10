"""Correlation ID middleware for request tracing."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagate or generate a correlation ID for every request.

    If the incoming request carries an ``X-Request-Id`` header the value is
    reused; otherwise a new UUID-4 is generated. The ID is stored in a
    ``ContextVar`` so that the structured logger can include it, and it is
    echoed back to the client in the response ``X-Request-Id`` header.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        cid = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        correlation_id_var.set(cid)
        response = await call_next(request)
        response.headers["X-Request-Id"] = cid
        return response
