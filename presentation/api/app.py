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
from contextlib import asynccontextmanager
from datetime import datetime, UTC
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.config.dependency_injection import Container
from infrastructure.logging_config import setup_logging
from infrastructure.persistence.database import init_db
from presentation.api.middleware.correlation import CorrelationIdMiddleware
from presentation.api.middleware.rate_limit import RateLimitMiddleware
from presentation.api.routers import analysis, auth, billing, github, jira, projects
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",    # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",    # CRA fallback
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


# ---------------------------------------------------------------------------
# Additional middleware (applied after CORS)
# ---------------------------------------------------------------------------

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------------
# Mount routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(analysis.router)
app.include_router(github.router)
app.include_router(jira.router)
app.include_router(billing.router)
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
