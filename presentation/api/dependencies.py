"""
FastAPI dependency injection — bridges the DI Container into request scope.

Architectural Intent:
    FastAPI's Depends() mechanism is the natural seam between the HTTP framework
    and the application's Composition Root. Dependencies defined here pull from
    the Container singleton initialised at application startup (stored in
    app.state) so that routers never import infrastructure directly.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from infrastructure.config.dependency_injection import Container
from presentation.api.schemas import UserInfo


# ---------------------------------------------------------------------------
# Container access
# ---------------------------------------------------------------------------

def get_container(request: Request) -> Container:
    """Return the DI Container initialised during application lifespan.

    The container is stored on ``app.state.container`` by the lifespan handler.
    """
    container: Container | None = getattr(request.app.state, "container", None)
    if container is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialised. Container unavailable.",
        )
    return container


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

_MVP_API_KEY: str | None = os.environ.get("STRATUM_API_KEY")


async def get_current_user(
    x_api_key: Annotated[str | None, Header()] = None,
) -> UserInfo:
    """Validate the request API key and return the authenticated user.

    MVP implementation:
    - If ``STRATUM_API_KEY`` env var is set, the request must provide a
      matching ``X-API-Key`` header.
    - If the env var is *not* set, authentication is open (development mode).
    - In Phase 2 this will be replaced with JWT / OAuth validation.
    """
    expected_key = _MVP_API_KEY or os.environ.get("STRATUM_API_KEY")

    if expected_key:
        if not x_api_key or x_api_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key. Provide X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    # In MVP, return a static user. Phase 2 will decode a JWT here.
    return UserInfo(
        user_id="usr_mvp_001",
        email="analyst@stratum.dev",
        name="Stratum Analyst",
        role="analyst",
    )
