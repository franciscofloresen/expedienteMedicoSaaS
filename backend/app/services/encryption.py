"""
Encryption Service — Direct KMS Encryption

Architecture:
  Directly uses AWS KMS to encrypt sensitive fields (e.g., patient addresses,
  medical background).
  The KMS Customer Master Key (CMK) provides AES-256-GCM encryption.
  The tenant_id is used as the EncryptionContext to cryptographically
  bind the data to the specific tenant, preventing cross-tenant access
  even if the database is compromised.
"""

from typing import Any, cast

import boto3
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

_kms_client = None

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
def encrypt_field(plaintext: str, tenant_id: str) -> bytes:
    """
    Encrypt a sensitive field directly using AWS KMS.

    Args:
        plaintext: The string to encrypt
        tenant_id: The tenant UUID (used for KMS Encryption Context)

    Returns:
        bytes: The ciphertext blob returned by KMS
    """
    if settings.environment in ("development", "testing"):
        # For local dev without AWS credentials, just return a mock bytes representation
        return f"MOCK-ENCRYPTED-{tenant_id}-{plaintext}".encode("utf-8")

    kms = _get_kms_client()
    response = kms.encrypt(
        KeyId=settings.kms_encryption_key_id,
        Plaintext=plaintext.encode("utf-8"),
        EncryptionContext={"tenant_id": str(tenant_id)},
    )
    return cast(bytes, response["CiphertextBlob"])


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
    reraise=True,
)
def decrypt_field(ciphertext_blob: bytes, tenant_id: str) -> str:
    """
    Decrypt a sensitive field directly using AWS KMS.

    Args:
        ciphertext_blob: The encrypted data from KMS
        tenant_id: The tenant UUID

    Returns:
        str: The decrypted plaintext
    """
    if settings.environment in ("development", "testing"):
        try:
            # Mock decryption logic for local dev
            decoded = ciphertext_blob.decode("utf-8")
            if decoded.startswith(f"MOCK-ENCRYPTED-{tenant_id}-"):
                return decoded.replace(f"MOCK-ENCRYPTED-{tenant_id}-", "", 1)
        except Exception:
            pass
        return "Decryption Error (Dev Mock)"

    kms = _get_kms_client()
    response = kms.decrypt(
        CiphertextBlob=ciphertext_blob,
        EncryptionContext={"tenant_id": str(tenant_id)},
    )
    plaintext = cast(bytes, response["Plaintext"])
    return plaintext.decode("utf-8")
