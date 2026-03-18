"""
Stratum FastAPI application — REST API for the code intelligence platform.

Architectural Intent:
    This is the HTTP entry point for the Stratum SaaS platform (Phase 2).
    It follows hexagonal architecture: the FastAPI app is an adapter in the
    presentation layer that converts HTTP requests into application-layer
    commands and queries. No domain logic lives here.

    - Lifespan handler initialises the DI Container once at startup.
    - Structured JSON logging configured before app creation.
    - CORS middleware configured for the React development server.
    - Correlation ID and rate-limit middleware for observability and protection.
    - Routers are thin HTTP adapters mounted under /api.
    - WebSocket endpoint mounted for real-time analysis progress.
    - OpenAPI docs available at /docs (Swagger UI) and /redoc (ReDoc).

Usage:
    uvicorn presentation.api.app:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import AsyncGenerator

from starlette.types import ASGIApp, Receive, Scope, Send

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from infrastructure.config.dependency_injection import Container
from infrastructure.logging_config import setup_logging
from infrastructure.persistence.database import init_db
from presentation.api.middleware.correlation import CorrelationIdMiddleware, correlation_id_var
from presentation.api.middleware.rate_limit import RateLimitMiddleware
from presentation.api.routers import analysis, auth, billing, github, jira, partner, projects
from presentation.api.routers import websocket
from presentation.api.schemas import HealthResponse

# Configure structured logging before anything else
setup_logging()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — initialise and tear down shared resources
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    On startup:
        - Create the DI Container (Composition Root) and store it on app.state.
        - Initialise the database (create tables if they don't exist).
        - All adapters are wired eagerly so misconfiguration fails fast.

    On shutdown:
        - Clean up resources if needed (currently no-op).
    """
    logger.info("Stratum API starting up — initialising dependency container")
    container = Container.create()
    app.state.container = container
    logger.info("Dependency container ready")

    logger.info("Initialising database")
    await init_db()
    logger.info("Database initialised")

    # Auto-seed demo data when STRATUM_SEED=1 or database is empty
    if os.environ.get("STRATUM_SEED", "").strip() == "1":
        from scripts.seed_data import seed
        logger.info("STRATUM_SEED=1 — loading demo data")
        await seed()

    yield

    logger.info("Stratum API shutting down")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Stratum Code Intelligence API",
    description=(
        "REST API for the Stratum code intelligence platform. "
        "Analyse git repositories across 15 quality dimensions, identify "
        "risk hotspots, and generate integrated risk reports."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ---------------------------------------------------------------------------
# CORS — allow React dev server
# ---------------------------------------------------------------------------

_default_origins = [
    "http://localhost:5173",    # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",    # CRA fallback
    "http://127.0.0.1:3000",
]

_cors_origins = (
    os.environ.get("CORS_ORIGINS", "").split(",")
    if os.environ.get("CORS_ORIGINS")
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-Id", "X-Partner-Key"],
    expose_headers=["X-Request-Id"],
)


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware:
    """ASGI middleware that adds standard security headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                ])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ---------------------------------------------------------------------------
# Additional middleware (applied after CORS)
# ---------------------------------------------------------------------------

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Logs the full traceback for debugging while returning a safe,
    non-leaking 500 response to the client. Includes the correlation ID
    so operators can correlate the client error with server-side logs.
    """
    request_id = correlation_id_var.get("")
    logger.exception("Unhandled exception (request_id=%s)", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(analysis.router)
app.include_router(github.router)
app.include_router(jira.router)
app.include_router(billing.router)
app.include_router(partner.router)
app.include_router(websocket.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Returns service health status, version, and current server time.",
)
async def health_check() -> HealthResponse:
    """Lightweight health check for load balancers and uptime monitors."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(UTC).isoformat(),
    )
