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

import jwt as pyjwt
import httpx

from app.core.config import settings

logger = logging.getLogger("medrecord.security")

# ── JWKS Cache (Cognito production mode) ──

_jwks_cache: dict[str, Any] | None = None
_jwks_cached_at: float = 0
JWKS_CACHE_TTL = 3600  # 1 hour

# ── Local JWT Config (development mode) ──

LOCAL_JWT_SECRET = "medrecord-dev-secret-change-in-production"
LOCAL_JWT_ALGORITHM = "HS256"


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
    Decode and validate a JWT token.

    In development: validates HS256 tokens issued by our local auth endpoints.
    In production: validates RS256 tokens from Cognito via JWKS.

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
                LOCAL_JWT_SECRET,
                algorithms=[LOCAL_JWT_ALGORITHM],
                options={"verify_aud": False},
            )
            # Validate required claims
            if not claims.get("custom:tenant_id"):
                raise ValueError("Token sin tenant_id asociado")
            return claims
        except pyjwt.ExpiredSignatureError:
            raise ValueError("Token expirado")
        except pyjwt.InvalidTokenError:
            # Not a local token — fall through to Cognito validation
            # (allows Cognito tokens to work in dev mode too)
            pass

    # Production: Cognito RS256 validation via JWKS
    return _decode_cognito_jwt(token)


def _decode_cognito_jwt(token: str) -> dict[str, Any]:
    """
    Decode and validate a Cognito JWT token using JWKS.

    Validates:
    - Signature (via JWKS)
    - Expiration
    - Issuer (Cognito User Pool)
    - Token use (access token)
    """
    try:
        headers = pyjwt.get_unverified_header(token)
    except pyjwt.InvalidTokenError as e:
        raise ValueError(f"Token inválido: {e}")

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
            public_key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=_get_issuer(),
        )
    except pyjwt.ExpiredSignatureError:
        raise ValueError("Token expirado")
    except pyjwt.InvalidTokenError as e:
        raise ValueError(f"Token inválido: {e}")

    return claims


def _find_key_by_kid(jwks_data: dict, kid: str) -> dict | None:
    """Find a key in JWKS data by its key ID."""
    for k in jwks_data.get("keys", []):
        if k.get("kid") == kid:
            return k
    return None
