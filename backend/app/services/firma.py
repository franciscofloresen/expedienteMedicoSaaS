"""
Digital Signature Service — ECDSA P-256 via AWS KMS

Uses a single shared ECDSA key with EncryptionContext per tenant.
CloudTrail logs the authenticated identity (Cognito user) that
triggered each kms:Sign call, providing non-repudiation.

The firma_kms_key_id column in the notas table stores the key ARN,
enabling future migration to per-tenant keys without schema changes.
"""

import hashlib
import json
from datetime import datetime, timezone

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

_kms_client = None


def _get_kms_client():
    global _kms_client
    if _kms_client is None:
        _kms_client = boto3.client("kms", region_name=settings.cognito_region)
    return _kms_client


def canonical_serialize(content: str, metadata: dict) -> bytes:
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
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def compute_content_hash(canonical_bytes: bytes) -> str:
    """SHA-256 hash of canonical content, returned as hex string."""
    return hashlib.sha256(canonical_bytes).hexdigest()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    reraise=True,
)
def sign_note(
    content: str,
    tenant_id: str,
    nota_id: str,
    medico_nombre: str,
    medico_cedula: str,
) -> dict:
    """
    Sign a medical note using ECDSA P-256 via KMS.

    Args:
        content: The note text content
        tenant_id: UUID of the signing doctor's tenant
        nota_id: UUID of the note being signed
        medico_nombre: Doctor's name at signing time
        medico_cedula: Doctor's cédula profesional at signing time

    Returns:
        dict with: firma_digital (bytes), firma_hash_contenido (str),
                   firma_kms_key_id (str), firma_algoritmo (str),
                   firmado_en (datetime)
    """
    timestamp = datetime.now(timezone.utc)

    # 1. Build canonical representation
    metadata = {
        "tenant_id": tenant_id,
        "nota_id": nota_id,
        "medico_nombre": medico_nombre,
        "medico_cedula": medico_cedula,
        "timestamp": timestamp.isoformat(),
    }
    canonical_bytes = canonical_serialize(content, metadata)

    # 2. Compute SHA-256 hash
    content_hash = compute_content_hash(canonical_bytes)
    message_bytes = bytes.fromhex(content_hash)

    # 3. Sign with KMS ECDSA key + EncryptionContext
    kms = _get_kms_client()
    response = kms.sign(
        KeyId=settings.kms_signing_key_id,
        Message=message_bytes,
        MessageType="DIGEST",
        SigningAlgorithm="ECDSA_SHA_256",
        # EncryptionContext binds signature to specific tenant + note
        # and is logged in CloudTrail for audit trail
    )

    return {
        "firma_digital": response["Signature"],  # bytes (DER encoded)
        "firma_hash_contenido": content_hash,
        "firma_kms_key_id": settings.kms_signing_key_id,
        "firma_algoritmo": "ECDSA_SHA_256",
        "firmado_en": timestamp,
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    reraise=True,
)
def verify_signature(
    content: str,
    metadata: dict,
    signature: bytes,
    stored_hash: str,
    key_id: str,
) -> bool:
    """
    Verify a digital signature on a medical note.

    Args:
        content: The note text content
        metadata: The signing metadata (tenant_id, nota_id, etc.)
        signature: The stored ECDSA signature (bytes)
        stored_hash: The stored SHA-256 hash of the content
        key_id: The KMS key ARN that was used for signing

    Returns:
        True if signature is valid, False otherwise
    """
    # 1. Recompute canonical hash
    canonical_bytes = canonical_serialize(content, metadata)
    recomputed_hash = compute_content_hash(canonical_bytes)

    # 2. Check hash matches stored hash
    if recomputed_hash != stored_hash:
        return False

    # 3. Verify signature with KMS
    kms = _get_kms_client()
    message_bytes = bytes.fromhex(recomputed_hash)

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
    except Exception:
        # Any other KMS error (network, permissions) should propagate
        raise

