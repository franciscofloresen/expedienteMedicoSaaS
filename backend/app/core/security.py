"""JWT validation, mandatory MFA, and step-up authentication controls."""

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt as pyjwt
from fastapi import Request

from app.core.config import settings

logger = logging.getLogger("medrecord.security")

_jwks_cache: dict[str, Any] | None = None
_jwks_cached_at: float = 0
JWKS_CACHE_TTL = 3600
JWKS_TIMEOUT = httpx.Timeout(5.0, connect=2.0)

LOCAL_JWT_ALGORITHM = "HS256"
CLERK_JWT_ALGORITHM = "RS256"
_ephemeral_secret: str | None = None


class ReauthenticationRequiredError(Exception):
    """Raised when a sensitive action needs a fresh multi-factor verification."""


def _get_local_jwt_secret() -> str:
    """Return the configured development secret or a process-local random value."""
    global _ephemeral_secret
    if settings.jwt_dev_secret:
        return settings.jwt_dev_secret
    if _ephemeral_secret is None:
        import os

        _ephemeral_secret = os.urandom(32).hex()
        logger.warning(
            "JWT_DEV_SECRET is absent; using a process-local development key",
            extra={"error_code": "ephemeral_dev_jwt_key"},
        )
    return _ephemeral_secret


def _get_jwks_url() -> str:
    return settings.clerk_jwks_url


def _get_issuer() -> str:
    return settings.clerk_issuer_url.rstrip("/")


def _validate_clerk_configuration() -> None:
    issuer = urlparse(_get_issuer())
    jwks = urlparse(_get_jwks_url())
    if issuer.scheme != "https" or jwks.scheme != "https":
        raise ValueError("Configuración Clerk insegura")
    if not issuer.hostname or issuer.hostname != jwks.hostname:
        raise ValueError("Issuer y JWKS de Clerk no coinciden")
    if not settings.clerk_authorized_parties:
        raise ValueError("CLERK_AUTHORIZED_PARTIES no está configurado")


def _validated_jwks(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JWKS inválido")
    keys = payload.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ValueError("JWKS sin llaves")
    return payload


def _fetch_jwks(*, force_refresh: bool = False) -> dict[str, Any]:
    """Fetch and validate Clerk JWKS with a bounded cache and fail-closed timeout."""
    global _jwks_cache, _jwks_cached_at
    now = time.monotonic()
    if not force_refresh and _jwks_cache and now - _jwks_cached_at < JWKS_CACHE_TTL:
        return _jwks_cache

    _validate_clerk_configuration()
    response = httpx.get(
        _get_jwks_url(),
        timeout=JWKS_TIMEOUT,
        follow_redirects=False,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload = _validated_jwks(response.json())
    _jwks_cache = payload
    _jwks_cached_at = now
    return payload


def _find_key_by_kid(jwks_data: dict[str, Any], kid: str) -> dict[str, Any] | None:
    for key in jwks_data.get("keys", []):
        if not isinstance(key, dict) or key.get("kid") != kid:
            continue
        if key.get("kty") != "RSA":
            raise ValueError("Tipo de llave JWT no permitido")
        if key.get("use") not in (None, "sig"):
            raise ValueError("Uso de llave JWT no permitido")
        if key.get("alg") not in (None, CLERK_JWT_ALGORITHM):
            raise ValueError("Algoritmo de llave JWT no permitido")
        return key
    return None


def _validate_authorized_party(claims: dict[str, Any]) -> None:
    azp = claims.get("azp")
    if not isinstance(azp, str) or azp not in settings.clerk_authorized_parties:
        raise ValueError("Authorized party (azp) no permitida")


def _factor_ages(claims: dict[str, Any]) -> tuple[int, int] | None:
    fva = claims.get("fva")
    if (
        not isinstance(fva, list)
        or len(fva) != 2
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < -1
            for value in fva
        )
    ):
        return None
    return fva[0], fva[1]


def has_mfa(claims: dict[str, Any]) -> bool:
    """Return true only when Clerk reports an enrolled second factor."""
    ages = _factor_ages(claims)
    return ages is not None and ages[1] >= 0


def has_recent_reauthentication(claims: dict[str, Any], max_age_minutes: int) -> bool:
    """Mirror Clerk's strict_mfa policy without trusting frontend state."""
    ages = _factor_ages(claims)
    if ages is None:
        return False
    first_factor_age, second_factor_age = ages
    return (
        first_factor_age >= 0
        and second_factor_age >= 0
        and first_factor_age < max_age_minutes
        and second_factor_age < max_age_minutes
    )


def require_reauthentication(request: Request) -> None:
    """FastAPI dependency for signatures, credential changes, and legal revocations."""
    if settings.environment in ("development", "testing"):
        return
    # Step-up reauthentication is part of the same policy as MFA and relies on a
    # second factor being enrolled. When MFA enforcement is disabled (e.g. the
    # Clerk plan does not include MFA), this check is disabled too so sensitive
    # actions keep working with the normal session.
    if not settings.clerk_require_mfa:
        return
    claims = getattr(request.state, "auth_claims", {})
    if not has_recent_reauthentication(claims, settings.clerk_reauth_max_age_minutes):
        raise ReauthenticationRequiredError


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode a local development token or a fully validated Clerk session token."""
    if settings.environment == "development":
        try:
            return pyjwt.decode(
                token,
                _get_local_jwt_secret(),
                algorithms=[LOCAL_JWT_ALGORITHM],
                options={"verify_aud": False},
            )
        except pyjwt.ExpiredSignatureError as exc:
            raise ValueError("Token expirado") from exc
        except pyjwt.InvalidTokenError:
            pass
    return _decode_clerk_jwt(token)


def _decode_clerk_jwt(token: str) -> dict[str, Any]:
    """Validate Clerk signature, time claims, issuer, audience/azp, alg and kid."""
    try:
        headers = pyjwt.get_unverified_header(token)
    except pyjwt.InvalidTokenError as exc:
        raise ValueError("Token malformado") from exc

    if headers.get("alg") != CLERK_JWT_ALGORITHM:
        raise ValueError("Algoritmo JWT no permitido")
    kid = headers.get("kid")
    if not isinstance(kid, str) or not kid:
        raise ValueError("Token sin key ID (kid)")

    key = _find_key_by_kid(_fetch_jwks(), kid)
    if key is None:
        key = _find_key_by_kid(_fetch_jwks(force_refresh=True), kid)
    if key is None:
        raise ValueError("Llave de firma no encontrada")

    try:
        from jwt.algorithms import RSAAlgorithm

        public_key = RSAAlgorithm.from_jwk(key)
        decode_kwargs: dict[str, Any] = {
            "algorithms": [CLERK_JWT_ALGORITHM],
            "issuer": _get_issuer(),
            "leeway": 5,
            "options": {
                "require": ["exp", "iat", "nbf", "iss", "sub", "sid"],
                "verify_aud": bool(settings.clerk_audience),
            },
        }
        if settings.clerk_audience:
            decode_kwargs["audience"] = settings.clerk_audience
        claims = pyjwt.decode(token, public_key, **decode_kwargs)  # type: ignore[arg-type]
    except pyjwt.ExpiredSignatureError as exc:
        raise ValueError("Token expirado") from exc
    except pyjwt.InvalidTokenError as exc:
        raise ValueError("Token inválido") from exc

    _validate_authorized_party(claims)
    if claims.get("sts") == "pending":
        raise ValueError("Sesión Clerk pendiente")
    if claims.get("act") is not None:
        # Support impersonation is deliberately unavailable until a consented,
        # expiring and audited support-access model exists.
        raise ValueError("Impersonación de soporte no permitida")
    if settings.clerk_require_mfa and not has_mfa(claims):
        raise ValueError("MFA obligatorio")
    return claims
