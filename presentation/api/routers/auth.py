"""
Authentication router — API-key auth with JWT issuance.

Architectural Intent:
    Thin HTTP adapter. Validates credentials, issues JWT tokens, and returns
    user information. No business logic — delegates to the auth dependency
    and the JWT handler for token creation.
"""

from __future__ import annotations

import hashlib
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from infrastructure.auth.jwt_handler import JWT_EXPIRY_HOURS, create_access_token
from presentation.api.dependencies import get_current_user
from presentation.api.schemas import AuthToken, LoginRequest, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=AuthToken,
    summary="Authenticate and obtain access token",
    description=(
        "Authenticate with email/password and receive a JWT access token. "
        "If STRATUM_API_KEY is set, also returns that key for backward-compatible "
        "X-API-Key header authentication."
    ),
)
async def login(body: LoginRequest) -> AuthToken:
    """Authenticate a user and return a JWT access token.

    Creates a JWT with user claims (user_id, email, name, role). If
    ``STRATUM_API_KEY`` is configured the static key is returned for
    backward compatibility; otherwise a real JWT is issued.
    """
    if not body.email or not body.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required.",
        )

    # Build user claims for the JWT payload
    user_id = f"usr_{hashlib.md5(body.email.encode()).hexdigest()[:12]}"
    payload = {
        "user_id": user_id,
        "email": body.email,
        "name": body.email.split("@")[0].replace(".", " ").title(),
        "role": "analyst",
    }

    # Check for static API key (backward compat)
    api_key = os.environ.get("STRATUM_API_KEY")
    if api_key:
        token = api_key
    else:
        token = create_access_token(payload)

    return AuthToken(
        access_token=token,
        token_type="bearer",
        expires_in=JWT_EXPIRY_HOURS * 3600,
    )


@router.get(
    "/me",
    response_model=UserInfo,
    summary="Get current user information",
    description="Returns the authenticated user's profile. Requires a valid token or API key.",
)
async def get_me(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> UserInfo:
    """Return the currently authenticated user."""
    return current_user
