import base64
import json
import time
import uuid
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from app.core import security
from app.core.config import settings
from app.main import app, reauthentication_required_handler


def _b64url(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture
def clerk_signer(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "phase9-test-key",
        "n": _b64url(numbers.n),
        "e": _b64url(numbers.e),
    }
    monkeypatch.setattr(settings, "clerk_issuer_url", "https://issuer.example.test")
    monkeypatch.setattr(
        settings, "clerk_jwks_url", "https://issuer.example.test/.well-known/jwks.json"
    )
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://app.example.test"])
    monkeypatch.setattr(settings, "clerk_audience", "")
    monkeypatch.setattr(settings, "clerk_require_mfa", True)
    monkeypatch.setattr(security, "_fetch_jwks", lambda **_kwargs: {"keys": [jwk]})
    return private_key, jwk


def _claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": "https://issuer.example.test",
        "sub": "user_phase9",
        "sid": "sess_phase9",
        "azp": "https://app.example.test",
        "iat": now,
        "nbf": now - 1,
        "exp": now + 300,
        "fva": [0, 0],
    }
    claims.update(overrides)
    return claims


def _token(private_key: Any, claims: dict[str, Any], **headers: Any) -> str:
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "phase9-test-key", **headers},
    )


def test_valid_clerk_token_requires_mfa_and_authorized_party(
    clerk_signer: tuple[Any, dict[str, Any]],
) -> None:
    private_key, _ = clerk_signer
    decoded = security._decode_clerk_jwt(_token(private_key, _claims()))
    assert decoded["sub"] == "user_phase9"
    assert security.has_mfa(decoded)


@pytest.mark.parametrize(
    ("claim_changes", "message"),
    [
        ({"azp": "https://attacker.example"}, "Authorized party"),
        ({"fva": [0, -1]}, "MFA obligatorio"),
        ({"fva": [True, True]}, "MFA obligatorio"),
        ({"act": {"sub": "support_agent"}}, "Impersonación"),
        ({"exp": 1}, "Token expirado"),
        ({"iss": "https://wrong-issuer.example"}, "Token inválido"),
    ],
)
def test_clerk_token_negative_cases_fail_closed(
    clerk_signer: tuple[Any, dict[str, Any]],
    claim_changes: dict[str, Any],
    message: str,
) -> None:
    private_key, _ = clerk_signer
    with pytest.raises(ValueError, match=message):
        security._decode_clerk_jwt(_token(private_key, _claims(**claim_changes)))


def test_clerk_token_rejects_missing_kid_before_jwks_lookup(
    clerk_signer: tuple[Any, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _ = clerk_signer
    token = jwt.encode(_claims(), private_key, algorithm="RS256", headers={"kid": ""})
    monkeypatch.setattr(
        security,
        "_fetch_jwks",
        lambda **_kwargs: pytest.fail("JWKS must not be fetched for a missing kid"),
    )
    with pytest.raises(ValueError, match="kid"):
        security._decode_clerk_jwt(token)


def test_clerk_token_rejects_algorithm_confusion(clerk_signer: tuple[Any, dict[str, Any]]) -> None:
    token = jwt.encode(
        _claims(),
        "not-an-rsa-key-that-is-at-least-thirty-two-bytes",
        algorithm="HS256",
        headers={"kid": "phase9-test-key"},
    )
    with pytest.raises(ValueError, match="Algoritmo JWT no permitido"):
        security._decode_clerk_jwt(token)


def test_clerk_token_rejects_invalid_signature_and_missing_required_claim(
    clerk_signer: tuple[Any, dict[str, Any]],
) -> None:
    _private_key, _ = clerk_signer
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(ValueError, match="Token inválido"):
        security._decode_clerk_jwt(_token(attacker_key, _claims()))

    claims_without_session = _claims()
    claims_without_session.pop("sid")
    with pytest.raises(ValueError, match="Token inválido"):
        security._decode_clerk_jwt(_token(_private_key, claims_without_session))


def test_unknown_kid_refreshes_once_then_fails_closed(
    clerk_signer: tuple[Any, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _ = clerk_signer
    calls: list[bool] = []

    def empty_jwks(*, force_refresh: bool = False) -> dict[str, Any]:
        calls.append(force_refresh)
        return {"keys": []}

    monkeypatch.setattr(security, "_fetch_jwks", empty_jwks)
    with pytest.raises(ValueError, match="Llave de firma no encontrada"):
        security._decode_clerk_jwt(_token(private_key, _claims()))
    assert calls == [False, True]


def test_jwks_network_timeout_is_not_bypassed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "clerk_issuer_url", "https://issuer.example.test")
    monkeypatch.setattr(
        settings, "clerk_jwks_url", "https://issuer.example.test/.well-known/jwks.json"
    )
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://app.example.test"])
    monkeypatch.setattr(security, "_jwks_cache", None)

    def timed_out(*_args: Any, **_kwargs: Any) -> None:
        raise security.httpx.ReadTimeout("timeout")

    monkeypatch.setattr(security.httpx, "get", timed_out)
    with pytest.raises(security.httpx.ReadTimeout):
        security._fetch_jwks()


def test_clerk_audience_is_verified_when_configured(
    clerk_signer: tuple[Any, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _ = clerk_signer
    monkeypatch.setattr(settings, "clerk_audience", "clinical-api")
    with pytest.raises(ValueError, match="Token inválido"):
        security._decode_clerk_jwt(_token(private_key, _claims(aud="different-api")))
    decoded = security._decode_clerk_jwt(_token(private_key, _claims(aud="clinical-api")))
    assert decoded["aud"] == "clinical-api"


def test_jwks_payload_and_configuration_are_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="JWKS sin llaves"):
        security._validated_jwks({"keys": []})
    monkeypatch.setattr(settings, "clerk_issuer_url", "http://issuer.example.test")
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://other.example.test/jwks")
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://app.example.test"])
    with pytest.raises(ValueError, match="insegura"):
        security._validate_clerk_configuration()


def test_reauthentication_requires_two_recent_factors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "prod")
    monkeypatch.setattr(settings, "clerk_reauth_max_age_minutes", 10)
    request = SimpleNamespace(state=SimpleNamespace(auth_claims={"fva": [9, 9]}))
    assert security.require_reauthentication(request) is None  # type: ignore[arg-type]

    request.state.auth_claims = {"fva": [10, 0]}
    with pytest.raises(security.ReauthenticationRequiredError):
        security.require_reauthentication(request)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_reverification_response_matches_clerk_contract() -> None:
    expected = {
        "clerk_error": {
            "type": "forbidden",
            "reason": "reverification-error",
            "metadata": {"reverification": "strict_mfa"},
        }
    }
    response = await reauthentication_required_handler(  # type: ignore[arg-type]
        None, security.ReauthenticationRequiredError()
    )
    assert response.status_code == 403
    assert json.loads(response.body) == expected


@pytest.mark.asyncio
async def test_liveness_is_opaque_and_propagates_valid_request_id() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/live", headers={"X-Request-ID": "not-a-uuid"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "version" not in response.json()
    assert response.headers["X-Request-ID"] != "not-a-uuid"
    assert str(uuid.UUID(response.headers["X-Request-ID"])) == response.headers["X-Request-ID"]
