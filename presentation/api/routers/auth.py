"""
Authentication router — MVP API-key auth with JWT stub for Phase 2.

Architectural Intent:
    Thin HTTP adapter. Validates credentials, issues tokens, and returns
    user information. No business logic — delegates to the auth dependency.
"""

from __future__ import annotations

import hashlib
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from presentation.api.dependencies import get_current_user
from presentation.api.schemas import AuthToken, LoginRequest, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=AuthToken,
    summary="Authenticate and obtain access token",
    description=(
        "MVP: accepts any email/password and returns a token. "
        "If STRATUM_API_KEY is set, returns that key as the token. "
        "Phase 2 will implement real JWT issuance."
    ),
)
async def login(body: LoginRequest) -> AuthToken:
    """Authenticate a user and return an access token.

    MVP behaviour: if ``STRATUM_API_KEY`` is configured, the login
    endpoint returns it as the token so the client can use it in
    subsequent ``X-API-Key`` headers. If not configured, a
    deterministic token is generated from the email for local dev.
    """
    if not body.email or not body.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required.",
        )

    # In MVP, we accept any credentials.
    api_key = os.environ.get("STRATUM_API_KEY")
    if api_key:
        token = api_key
    else:
        # Deterministic dev token so repeated logins return the same value
        token = hashlib.sha256(
            f"stratum-dev-{body.email}".encode()
        ).hexdigest()

    return AuthToken(
        access_token=token,
        token_type="bearer",
        expires_in=86400,  # 24 hours
    )


@router.get(
    "/me",
    response_model=UserInfo,
    summary="Get current user information",
    description="Returns the authenticated user's profile. Requires a valid API key.",
)
async def get_me(
    current_user: Annotated[UserInfo, Depends(get_current_user)],
) -> UserInfo:
    """Return the currently authenticated user."""
    return current_user
