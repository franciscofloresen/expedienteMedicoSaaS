"""
JWT Token Validation — Dual-mode (Development + Cognito)

Development: Validates HS256 JWTs issued by the local auth endpoints.
Production: Validates RS256 JWTs from AWS Cognito via JWKS.

The TenantMiddleware calls decode_jwt() — it doesn't care which
mode issued the token as long as the claims contain `custom:tenant_id`.
"""

import logging
import time
from typing import Any

import httpx
import jwt as pyjwt

from app.core.config import settings

logger = logging.getLogger("medrecord.security")

# ── JWKS Cache (Clerk production mode) ──

_jwks_cache: dict[str, Any] | None = None
_jwks_cached_at: float = 0
JWKS_CACHE_TTL = 3600  # 1 hour

# ── Local JWT Config (development mode) ──
# SECURITY: The secret is NEVER hardcoded. It is read from the
# JWT_DEV_SECRET env var, or generated ephemerally per process.

LOCAL_JWT_ALGORITHM = "HS256"
_ephemeral_secret: str | None = None


def _get_local_jwt_secret() -> str:
    """
    Get the JWT signing secret for local development.

    Priority:
    1. JWT_DEV_SECRET env var (via settings) — for stable tokens across restarts.
    2. Ephemeral random secret — generated once per process, tokens expire on restart.

    NEVER hardcoded. NEVER committed to source control.
    """
    global _ephemeral_secret

    # Try configured secret first
    if settings.jwt_dev_secret:
        return settings.jwt_dev_secret

    # Generate ephemeral secret (tokens won't survive Lambda cold start — acceptable in dev)
    if _ephemeral_secret is None:
        import os

        _ephemeral_secret = os.urandom(32).hex()
        logger.warning(
            "No JWT_DEV_SECRET configured — using ephemeral secret. "
            "Tokens will be invalidated on process restart. "
            "Set JWT_DEV_SECRET in .env.local for persistent dev sessions."
        )
    return _ephemeral_secret


def _get_jwks_url() -> str:
    return settings.clerk_jwks_url


def _get_issuer() -> str:
    return settings.clerk_issuer_url


def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Clerk with caching."""
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
    Decode and validate a JWT token.

    In development: validates HS256 tokens issued by our local auth endpoints.
    In production: validates RS256 tokens from Clerk via JWKS.

    Returns:
        dict: Token claims including sub, email, custom:tenant_id

    Raises:
        ValueError: If token is invalid, expired, or missing required claims
    """
    # Try local HS256 first in development mode
    if settings.environment == "development":
        try:
            claims = pyjwt.decode(
                token,
                _get_local_jwt_secret(),
                algorithms=[LOCAL_JWT_ALGORITHM],
                options={"verify_aud": False},
            )
            return claims
        except pyjwt.ExpiredSignatureError as e:
            raise ValueError("Token expirado") from e
        except pyjwt.InvalidTokenError:
            # Not a local token — fall through to Clerk validation
            pass

    # Production: Clerk RS256 validation via JWKS
    return _decode_clerk_jwt(token)


def _decode_clerk_jwt(token: str) -> dict[str, Any]:
    """
    Decode and validate a Clerk JWT token using JWKS.

    Validates:
    - Signature (via JWKS)
    - Expiration
    - Issuer (Clerk)
    """
    try:
        headers = pyjwt.get_unverified_header(token)
    except pyjwt.InvalidTokenError as e:
        raise ValueError(f"Token inválido: {e}") from e

    kid = headers.get("kid")
    if not kid:
        raise ValueError("Token sin key ID (kid)")

    # Find the matching key in JWKS
    jwks_data = _fetch_jwks()
    key = _find_key_by_kid(jwks_data, kid)

    if not key:
        # Key not found — JWKS might be stale, force refresh
        global _jwks_cached_at
        _jwks_cached_at = 0
        jwks_data = _fetch_jwks()
        key = _find_key_by_kid(jwks_data, kid)

    if not key:
        raise ValueError("Llave de firma no encontrada en JWKS")

    # Decode and validate
    try:
        # Convert JWK to PEM for PyJWT
        from jwt.algorithms import RSAAlgorithm

        public_key = RSAAlgorithm.from_jwk(key)

        claims = pyjwt.decode(
            token,
            public_key,  # type: ignore[arg-type]
            algorithms=["RS256"],
            # Clerk doesn't strictly enforce standard audience in all tokens unless configured
            options={"verify_aud": False},
            issuer=_get_issuer(),
        )
    except pyjwt.ExpiredSignatureError as e:
        raise ValueError("Token expirado") from e
    except pyjwt.InvalidTokenError as e:
        raise ValueError(f"Token inválido: {e}") from e

    return claims


def _find_key_by_kid(jwks_data: dict[str, Any], kid: str) -> dict[str, Any] | None:
    """Find a key in JWKS data by its key ID."""
    for k in jwks_data.get("keys", []):
        if k.get("kid") == kid:
            return k  # type: ignore[no-any-return]
    return None
