from unittest.mock import MagicMock, patch

from app.services.encryption import decrypt_field, encrypt_field
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
    assert (
        hash_hex == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


@patch("app.services.encryption.settings")
@patch("app.services.encryption._get_kms_client")
def test_encryption_decryption_flow(mock_get_kms, mock_settings):
    """Test encryption logic with mocked KMS directly."""
    mock_settings.environment = "production"
    mock_settings.kms_encryption_key_id = "test-key-id"

    # Mock KMS response for encrypt and decrypt
    mock_kms = MagicMock()
    mock_get_kms.return_value = mock_kms

    fake_ciphertext = b"fake-ciphertext-blob"
    mock_kms.encrypt.return_value = {"CiphertextBlob": fake_ciphertext}

    plaintext = "sensitive clinical data"
    mock_kms.decrypt.return_value = {"Plaintext": plaintext.encode("utf-8")}

    tenant_id = "1234-5678"

    # 1. Encrypt
    ciphertext = encrypt_field(plaintext, tenant_id)

    # KMS Encrypt should have been called once
    assert mock_kms.encrypt.call_count == 1
    assert ciphertext == fake_ciphertext

    # 2. Decrypt
    decrypted = decrypt_field(ciphertext, tenant_id)

    # KMS Decrypt should have been called once
    assert mock_kms.decrypt.call_count == 1
    assert decrypted == plaintext
