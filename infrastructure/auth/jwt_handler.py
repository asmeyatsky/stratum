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

import logging
import os
from datetime import datetime, timedelta, UTC

import jwt

logger = logging.getLogger(__name__)

_DEV_SECRET = "stratum-dev-only-not-for-production"


def _resolve_jwt_secret() -> str:
    """Resolve the JWT signing secret from environment.

    - If ``JWT_SECRET`` is set, use it.
    - If ``STRATUM_DEV_MODE=true``, fall back to a dev-only secret and log a
      warning.
    - Otherwise raise ``RuntimeError`` to prevent startup with no secret.
    """
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret

    if os.environ.get("STRATUM_DEV_MODE", "").lower() == "true":
        logger.warning(
            "JWT_SECRET not set — using dev-only secret because STRATUM_DEV_MODE=true. "
            "Do NOT use this in production."
        )
        return _DEV_SECRET

    raise RuntimeError(
        "JWT_SECRET environment variable is required. "
        "Set STRATUM_DEV_MODE=true to use a development-only secret."
    )


JWT_SECRET: str = _resolve_jwt_secret()
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
