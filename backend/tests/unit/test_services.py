import os
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.services.encryption import encrypt_field, decrypt_field, clear_dek_cache
from app.services.firma import canonical_serialize, compute_content_hash


def test_canonical_serialize():
    """Ensures JSON serialization is deterministic regardless of key order."""
    metadata_1 = {"b": 2, "a": 1}
    metadata_2 = {"a": 1, "b": 2}
    
    bytes_1 = canonical_serialize("content", metadata_1)
    bytes_2 = canonical_serialize("content", metadata_2)
    
    assert bytes_1 == bytes_2
    assert b"content" in bytes_1


def test_compute_content_hash():
    """Ensures hash computation is consistent."""
    content_bytes = b"hello world"
    hash_hex = compute_content_hash(content_bytes)
    
    # sha256 of "hello world"
    assert hash_hex == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


@patch("app.services.encryption._get_kms_client")
def test_encryption_decryption_flow(mock_get_kms):
    """Test envelope encryption logic with mocked KMS."""
    
    # Mock KMS response for decrypt (returns our fake DEK)
    mock_kms = MagicMock()
    mock_get_kms.return_value = mock_kms
    
    fake_dek = os.urandom(32)  # AES-256 key
    mock_kms.decrypt.return_value = {"Plaintext": fake_dek}
    
    tenant_id = "1234-5678"
    fake_encrypted_dek = b"fake-encrypted-dek"
    
    # Clear cache to force KMS call
    clear_dek_cache()
    
    # 1. Encrypt
    plaintext = "sensitive clinical data"
    ciphertext = encrypt_field(plaintext, fake_encrypted_dek, tenant_id)
    
    # KMS Decrypt should have been called once
    assert mock_kms.decrypt.call_count == 1
    
    # 2. Decrypt
    decrypted = decrypt_field(ciphertext, fake_encrypted_dek, tenant_id)
    
    # KMS Decrypt should NOT have been called again (cache hit)
    assert mock_kms.decrypt.call_count == 1
    assert decrypted == plaintext
