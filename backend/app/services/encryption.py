"""
Envelope Encryption Service — KMS CMK + Per-Tenant DEKs

Architecture:
  1 symmetric CMK (AES-256) generates Data Encryption Keys (DEKs)
  Each tenant gets a unique DEK, stored encrypted in tenant_keys table
  DEK caching in Lambda memory reduces KMS API calls by ~95%

Cost: $1/month (CMK) + ~$0.03/10K API calls
"""

import os
import time
from typing import Any

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

_kms_client = None

# In-memory DEK cache: tenant_id -> (timestamp, plaintext_dek)
_dek_cache: dict[str, tuple[float, bytes]] = {}


def _get_kms_client() -> Any:
    global _kms_client
    if _kms_client is None:
        _kms_client = boto3.client("kms", region_name=settings.aws_region)
    return _kms_client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    reraise=True,
)
def generate_tenant_dek(tenant_id: str) -> dict[str, Any]:
    """
    Generate a new Data Encryption Key for a tenant.

    Called once during tenant onboarding. The plaintext DEK is NEVER stored —
    only the encrypted (ciphertext) version is persisted in the database.

    Returns:
        dict with encrypted_dek (bytes) and kms_key_id (str)
    """
    kms = _get_kms_client()
    response = kms.generate_data_key(
        KeyId=settings.kms_encryption_key_id,
        KeySpec="AES_256",
        EncryptionContext={"tenant_id": tenant_id},
    )

    # The plaintext is used only for immediate operations, then discarded
    # The ciphertext blob is stored in the database
    return {
        "plaintext_dek": response["Plaintext"],       # Use immediately, then discard
        "encrypted_dek": response["CiphertextBlob"],   # Store in tenant_keys table
        "kms_key_id": settings.kms_encryption_key_id,
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    reraise=True,
)
def _decrypt_dek(encrypted_dek: bytes, tenant_id: str) -> bytes:
    """Decrypt a tenant's DEK using the CMK."""
    if settings.environment in ("development", "testing"):
        return encrypted_dek  # En dev/testing usamos la llave en crudo como mock

    kms = _get_kms_client()
    response = kms.decrypt(
        CiphertextBlob=encrypted_dek,
        EncryptionContext={"tenant_id": tenant_id},
    )
    return response["Plaintext"]  # type: ignore[no-any-return]


def _get_plaintext_dek(encrypted_dek: bytes, tenant_id: str) -> bytes:
    """
    Get plaintext DEK with in-memory caching.

    Cache TTL is configurable (default 5 minutes).
    This reduces KMS Decrypt API calls by ~95% during normal operation.
    """
    now = time.time()

    if tenant_id in _dek_cache:
        cached_at, plaintext = _dek_cache[tenant_id]
        if now - cached_at < settings.dek_cache_ttl:
            return plaintext

    plaintext = _decrypt_dek(encrypted_dek, tenant_id)
    _dek_cache[tenant_id] = (now, plaintext)
    return plaintext


def encrypt_field(plaintext: str, encrypted_dek: bytes, tenant_id: str) -> bytes:
    """
    Encrypt a sensitive field using the tenant's DEK.

    Uses AES-256-GCM (authenticated encryption) which provides both
    confidentiality and integrity. The 12-byte nonce is prepended to
    the ciphertext for storage.

    Args:
        plaintext: The string to encrypt
        encrypted_dek: The tenant's encrypted DEK (from tenant_keys table)
        tenant_id: The tenant UUID (used for DEK decryption context)

    Returns:
        bytes: nonce (12 bytes) + ciphertext + auth_tag (16 bytes)
    """
    dek = _get_plaintext_dek(encrypted_dek, tenant_id)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(dek)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ciphertext  # nonce is needed for decryption


def decrypt_field(ciphertext_with_nonce: bytes, encrypted_dek: bytes, tenant_id: str) -> str:
    """
    Decrypt a sensitive field using the tenant's DEK.

    Args:
        ciphertext_with_nonce: The encrypted data (nonce + ciphertext + tag)
        encrypted_dek: The tenant's encrypted DEK
        tenant_id: The tenant UUID

    Returns:
        str: The decrypted plaintext

    Raises:
        cryptography.exceptions.InvalidTag: If data has been tampered with
    """
    dek = _get_plaintext_dek(encrypted_dek, tenant_id)
    nonce = ciphertext_with_nonce[:12]
    ciphertext = ciphertext_with_nonce[12:]
    aesgcm = AESGCM(dek)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode("utf-8")


def clear_dek_cache(tenant_id: str | None = None) -> None:
    """
    Clear the DEK cache. Called after key rotation.

    Args:
        tenant_id: Clear only this tenant's cache. None = clear all.
    """
    if tenant_id:
        _dek_cache.pop(tenant_id, None)
    else:
        _dek_cache.clear()
