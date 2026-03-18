"""
FastAPI dependency injection — bridges the DI Container into request scope.

Architectural Intent:
    FastAPI's Depends() mechanism is the natural seam between the HTTP framework
    and the application's Composition Root. Dependencies defined here pull from
    the Container singleton initialised at application startup (stored in
    app.state) so that routers never import infrastructure directly.

    Authentication supports three strategies (checked in order):
    1. ``Authorization: Bearer <JWT>`` header — decoded via PyJWT.
    2. ``X-API-Key`` header — matched against ``STRATUM_API_KEY`` env var.
    3. Dev mode — if no ``STRATUM_API_KEY`` is set, a static user is returned.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from infrastructure.auth.jwt_handler import decode_access_token
from infrastructure.config.dependency_injection import Container
from presentation.api.schemas import UserInfo

logger = logging.getLogger(__name__)


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

async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> UserInfo:
    """Validate the request credentials and return the authenticated user.

    Authentication strategies (checked in order):

    1. **JWT Bearer token** — ``Authorization: Bearer <token>`` header is
       decoded and its claims mapped to ``UserInfo``.
    2. **Static API key** — ``X-API-Key`` header is compared against the
       ``STRATUM_API_KEY`` environment variable.
    3. **Dev mode** — if ``STRATUM_API_KEY`` is not set and no token is
       provided, a static development user is returned.
    """
    # --- Strategy 1: JWT Bearer token ---
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            try:
                payload = decode_access_token(token)
                return UserInfo(
                    user_id=payload.get("user_id", "unknown"),
                    email=payload.get("email", "unknown@stratum.dev"),
                    name=payload.get("name", "Unknown User"),
                    role=payload.get("role", "analyst"),
                )
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired. Please log in again.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            except jwt.InvalidTokenError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token. Please provide a valid JWT.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    # --- Strategy 2: Static API key ---
    expected_key = os.environ.get("STRATUM_API_KEY")

    if expected_key:
        if x_api_key and x_api_key == expected_key:
            return UserInfo(
                user_id="usr_apikey_001",
                email="apikey@stratum.dev",
                name="API Key User",
                role="analyst",
            )
        # If an API key is configured, require valid auth
        if not x_api_key and not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide Authorization or X-API-Key header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if x_api_key and x_api_key != expected_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    # --- Strategy 3: Dev mode (only when STRATUM_DEV_MODE=true) ---
    if os.environ.get("STRATUM_DEV_MODE", "").lower() == "true":
        logger.warning(
            "Dev mode auth bypass active — returning static user. "
            "Do NOT use STRATUM_DEV_MODE=true in production."
        )
        return UserInfo(
            user_id="usr_mvp_001",
            email="analyst@stratum.dev",
            name="Stratum Analyst",
            role="analyst",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Authorization or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )
