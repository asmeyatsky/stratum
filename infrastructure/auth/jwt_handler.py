"""
JWT creation and validation for Stratum authentication.

Architectural Intent:
    Thin wrapper around PyJWT that centralises token configuration
    (secret, algorithm, expiry) in one place. All configuration is
    sourced from environment variables with safe development defaults.

    Callers should catch ``jwt.InvalidTokenError`` (parent of
    ``ExpiredSignatureError``, ``DecodeError``, etc.) for uniform
    error handling.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, UTC

import jwt

JWT_SECRET: str = os.environ.get(
    "JWT_SECRET",
    "stratum-dev-secret-change-in-production",
)
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_HOURS: int = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))


def create_access_token(payload: dict) -> str:
    """Create a signed JWT containing the given payload claims.

    An ``exp`` (expiry) and ``iat`` (issued-at) claim are added
    automatically.

    Args:
        payload: Arbitrary claims to embed (e.g. user_id, email, role).

    Returns:
        An encoded JWT string.
    """
    now = datetime.now(UTC)
    to_encode = {
        **payload,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT, returning the payload claims.

    Args:
        token: The encoded JWT string.

    Returns:
        The decoded payload dictionary.

    Raises:
        jwt.InvalidTokenError: If the token is malformed, expired, or
            the signature does not match.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
