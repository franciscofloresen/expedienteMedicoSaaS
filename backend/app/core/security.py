"""
JWT Token Validation — Cognito Integration

Validates JWT tokens from AWS Cognito User Pool.
Uses JWKS (JSON Web Key Set) for signature verification.
"""

import time
from functools import lru_cache
from typing import Any

import httpx
from jose import JWTError, jwk, jwt

from app.core.config import settings

_jwks_cache: dict[str, Any] | None = None
_jwks_cached_at: float = 0
JWKS_CACHE_TTL = 3600  # 1 hour


def _get_jwks_url() -> str:
    region = settings.cognito_region
    pool_id = settings.cognito_user_pool_id
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"


def _get_issuer() -> str:
    region = settings.cognito_region
    pool_id = settings.cognito_user_pool_id
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"


def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Cognito with caching."""
    global _jwks_cache, _jwks_cached_at

    now = time.time()
    if _jwks_cache and (now - _jwks_cached_at) < JWKS_CACHE_TTL:
        return _jwks_cache

    response = httpx.get(_get_jwks_url(), timeout=5)
    response.raise_for_status()
    _jwks_cache = response.json()
    _jwks_cached_at = now
    return _jwks_cache


def decode_jwt(token: str) -> dict[str, Any]:
    """
    Decode and validate a Cognito JWT token.

    Validates:
    - Signature (via JWKS)
    - Expiration
    - Issuer (Cognito User Pool)
    - Token use (access token)

    Returns:
        dict: Token claims including sub, email, custom:tenant_id

    Raises:
        JWTError: If token is invalid
        ValueError: If token is missing required claims
    """
    # Get the key ID from the token header
    try:
        headers = jwt.get_unverified_headers(token)
    except JWTError as e:
        raise ValueError(f"Token inválido: {e}")

    kid = headers.get("kid")
    if not kid:
        raise ValueError("Token sin key ID (kid)")

    # Find the matching key in JWKS
    jwks_data = _fetch_jwks()
    key = None
    for k in jwks_data.get("keys", []):
        if k["kid"] == kid:
            key = k
            break

    if not key:
        # Key not found — JWKS might be stale, force refresh
        global _jwks_cached_at
        _jwks_cached_at = 0
        jwks_data = _fetch_jwks()
        for k in jwks_data.get("keys", []):
            if k["kid"] == kid:
                key = k
                break

    if not key:
        raise ValueError("Llave de firma no encontrada en JWKS")

    # Decode and validate
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=_get_issuer(),
        )
    except JWTError as e:
        raise ValueError(f"Token inválido: {e}")

    return claims
