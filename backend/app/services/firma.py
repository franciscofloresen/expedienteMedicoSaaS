"""
Digital Signature Service — ECDSA P-256 via AWS KMS (Production) / Local Key (Development)

Production: Uses a shared KMS ECDSA key. CloudTrail logs the authenticated identity
(Cognito user) that triggered each kms:Sign call, providing non-repudiation.

Development: Uses a locally-generated ECDSA key for offline testing.
The local key is NOT suitable for production — it has no non-repudiation guarantees.

The canonical signed payload includes all context needed for legal audit:
tenant_id, nota_id, doctor identity snapshot, and timestamp. This is the approach
chosen because KMS asymmetric signing (kms:Sign) does NOT support EncryptionContext.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger("medrecord.firma")

_kms_client = None
_local_key = None


def _get_kms_client() -> Any:
    global _kms_client
    if _kms_client is None:
        import boto3

        _kms_client = boto3.client("kms", region_name=settings.aws_region)
    return _kms_client


def _get_local_key() -> Any:
    """
    Generate or return a local ECDSA P-256 key for development signing.
    This key is ephemeral — it lives only in process memory.
    """
    global _local_key
    if _local_key is None:
        from cryptography.hazmat.primitives.asymmetric import ec

        _local_key = ec.generate_private_key(ec.SECP256R1())
        logger.warning(
            "Using LOCAL development signing key. This is NOT suitable for production."
        )
    return _local_key


def canonical_serialize(content: str, metadata: dict[str, Any]) -> bytes:
    """
    Create a canonical representation of the note content for signing.

    Canonical form: JSON with sorted keys, no whitespace, UTF-8 encoded.
    This ensures the same content always produces the same hash,
    regardless of key ordering in the original dict.
    """
    canonical = {
        "contenido": content,
        "metadata": {k: str(v) for k, v in sorted(metadata.items())},
    }
    return json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_content_hash(canonical_bytes: bytes) -> str:
    """SHA-256 hash of canonical content, returned as hex string."""
    return hashlib.sha256(canonical_bytes).hexdigest()


def sign_note(
    content: str,
    tenant_id: str,
    nota_id: str,
    medico_nombre: str,
    medico_cedula: str,
    medico_especialidad: str = "",
) -> dict[str, Any]:
    """
    Sign a medical note using ECDSA P-256.

    In production: via AWS KMS.
    In development: via a local ephemeral key.

    The canonical signed payload includes all legal and audit context:
    tenant_id, nota_id, doctor name, cédula, especialidad, and timestamp.
    This compensates for the fact that KMS asymmetric signing does NOT
    support EncryptionContext.

    Args:
        content: The note text content
        tenant_id: UUID of the signing doctor's tenant
        nota_id: UUID of the note being signed
        medico_nombre: Doctor's name at signing time
        medico_cedula: Doctor's cédula profesional at signing time
        medico_especialidad: Doctor's specialty at signing time

    Returns:
        dict with: firma_digital (bytes), firma_hash_contenido (str),
                   firma_kms_key_id (str), firma_algoritmo (str),
                   firmado_en (datetime), medico_nombre (str),
                   medico_cedula (str), medico_especialidad (str)
    """
    timestamp = datetime.now(timezone.utc)

    # 1. Build canonical representation with all legal context
    metadata = {
        "tenant_id": tenant_id,
        "nota_id": nota_id,
        "medico_nombre": medico_nombre,
        "medico_cedula": medico_cedula,
        "medico_especialidad": medico_especialidad,
        "timestamp": timestamp.isoformat(),
    }
    canonical_bytes = canonical_serialize(content, metadata)

    # 2. Compute SHA-256 hash
    content_hash = compute_content_hash(canonical_bytes)

    # 3. Sign — route to KMS or local key based on environment
    if settings.environment != "development" and settings.kms_signing_key_id:
        signature, key_id = _sign_with_kms(content_hash)
    else:
        signature, key_id = _sign_with_local_key(content_hash)

    return {
        "firma_digital": signature,
        "firma_hash_contenido": content_hash,
        "firma_kms_key_id": key_id,
        "firma_algoritmo": "ECDSA_SHA_256",
        "firmado_en": timestamp,
        "medico_nombre": medico_nombre,
        "medico_cedula": medico_cedula,
        "medico_especialidad": medico_especialidad,
    }


def _sign_with_kms(content_hash: str) -> tuple[bytes, str]:
    """Sign using AWS KMS ECDSA key (production)."""
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
        reraise=True,
    )
    def _do_sign() -> Any:
        kms = _get_kms_client()
        message_bytes = bytes.fromhex(content_hash)
        response = kms.sign(
            KeyId=settings.kms_signing_key_id,
            Message=message_bytes,
            MessageType="DIGEST",
            SigningAlgorithm="ECDSA_SHA_256",
        )
        return response["Signature"], settings.kms_signing_key_id

    return _do_sign()  # type: ignore[no-any-return]


def _sign_with_local_key(content_hash: str) -> tuple[bytes, str]:
    """Sign using a local ECDSA key (development only)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    private_key = _get_local_key()
    message_bytes = bytes.fromhex(content_hash)

    signature = private_key.sign(
        message_bytes,
        ec.ECDSA(utils.Prehashed(hashes.SHA256())),
    )
    return signature, "local-dev-key"


def verify_signature(
    content: str,
    metadata: dict[str, Any],
    signature: bytes,
    stored_hash: str,
    key_id: str,
) -> bool:
    """
    Verify a digital signature on a medical note.

    Routes to KMS or local key verification based on the key_id.

    Args:
        content: The note text content
        metadata: The signing metadata (tenant_id, nota_id, etc.)
        signature: The stored ECDSA signature (bytes)
        stored_hash: The stored SHA-256 hash of the content
        key_id: The KMS key ARN or "local-dev-key"

    Returns:
        True if signature is valid, False otherwise
    """
    # 1. Recompute canonical hash
    canonical_bytes = canonical_serialize(content, metadata)
    recomputed_hash = compute_content_hash(canonical_bytes)

    # 2. Check hash matches stored hash
    if recomputed_hash != stored_hash:
        return False

    # 3. Verify signature
    if key_id == "local-dev-key":
        return _verify_with_local_key(recomputed_hash, signature)
    else:
        return _verify_with_kms(recomputed_hash, signature, key_id)


def _verify_with_kms(content_hash: str, signature: bytes, key_id: str) -> bool:
    """Verify using AWS KMS (production)."""
    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
        reraise=True,
    )
    def _do_verify() -> Any:
        kms = _get_kms_client()
        message_bytes = bytes.fromhex(content_hash)
        try:
            response = kms.verify(
                KeyId=key_id,
                Message=message_bytes,
                MessageType="DIGEST",
                Signature=signature,
                SigningAlgorithm="ECDSA_SHA_256",
            )
            return response.get("SignatureValid", False)
        except kms.exceptions.KMSInvalidSignatureException:
            return False

    return _do_verify()  # type: ignore[no-any-return]


def _verify_with_local_key(content_hash: str, signature: bytes) -> bool:
    """Verify using the local ECDSA key (development only)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils

    private_key = _get_local_key()
    public_key = private_key.public_key()
    message_bytes = bytes.fromhex(content_hash)

    try:
        public_key.verify(
            signature,
            message_bytes,
            ec.ECDSA(utils.Prehashed(hashes.SHA256())),
        )
        return True
    except Exception:
        return False
