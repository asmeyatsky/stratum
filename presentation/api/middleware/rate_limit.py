"""
Simple in-memory token-bucket rate limiter middleware.

Architectural Intent:
    Protects the API from excessive request rates per client IP.  Uses a
    token-bucket algorithm: each client starts with a burst-sized bucket
    that refills at a steady rate (RPM / 60 tokens per second).  When the
    bucket is empty the middleware returns 429 Too Many Requests with a
    ``Retry-After`` header.

    Health and documentation endpoints are excluded so that monitoring
    probes and Swagger UI remain unaffected.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

# Paths that bypass rate limiting
_EXEMPT_PATHS: set[str] = {"/api/health", "/docs", "/redoc", "/openapi.json"}

# Configuration via environment, with sensible defaults
_RPM: int = int(os.environ.get("RATE_LIMIT_RPM", "60"))
_BURST: int = int(os.environ.get("RATE_LIMIT_BURST", "10"))


@dataclass
class _TokenBucket:
    """Per-client token bucket state."""

    tokens: float = field(default_factory=lambda: float(_BURST))
    last_refill: float = field(default_factory=time.monotonic)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter scoped to client IP."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._buckets: dict[str, _TokenBucket] = defaultdict(_TokenBucket)
        self._rpm: int = _RPM
        self._burst: int = _BURST
        # Tokens added per second
        self._refill_rate: float = self._rpm / 60.0

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting ``X-Forwarded-For`` if present."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        bucket = self._buckets[client_ip]

        # Refill tokens based on elapsed time
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        bucket.tokens = min(
            float(self._burst),
            bucket.tokens + elapsed * self._refill_rate,
        )
        bucket.last_refill = now

        if bucket.tokens < 1.0:
            # Calculate seconds until one token is available
            retry_after = int((1.0 - bucket.tokens) / self._refill_rate) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry later."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Consume one token
        bucket.tokens -= 1.0

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        return response
