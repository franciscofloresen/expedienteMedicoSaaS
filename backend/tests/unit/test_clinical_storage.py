import pytest

from app.services import clinical_storage
from app.services.clinical_storage import validate_upload


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_type"),
    [
        ("resultado.pdf", "application/pdf", "application/pdf"),
        ("radiografia.JPG", "image/jpeg", "image/jpeg"),
        ("estudio.dcm", "application/octet-stream", "application/dicom"),
    ],
)
def test_validate_upload_accepts_clinical_formats(filename, content_type, expected_type):
    safe_name, normalized_type = validate_upload(filename, content_type, 1024)
    assert safe_name == filename
    assert normalized_type == expected_type


def test_validate_upload_strips_client_paths():
    safe_name, _ = validate_upload("/client/path/resultado.pdf", "application/pdf", 1024)
    assert safe_name == "resultado.pdf"
    windows_name, _ = validate_upload("C:\\fakepath\\radiografia.jpg", "image/jpeg", 1024)
    assert windows_name == "radiografia.jpg"


@pytest.mark.parametrize(
    ("filename", "content_type", "size_bytes"),
    [
        ("script.exe", "application/octet-stream", 1024),
        ("resultado.pdf", "application/pdf", 0),
        ("resultado.pdf", "application/pdf", 251 * 1024 * 1024),
    ],
)
def test_validate_upload_rejects_unsafe_input(filename, content_type, size_bytes):
    with pytest.raises(ValueError):
        validate_upload(filename, content_type, size_bytes)


def test_presigned_post_is_signed_with_sigv4(monkeypatch):
    # S3 rejects presigned requests specifying SSE-KMS unless signed with
    # SigV4; boto3 defaults presigning to legacy SigV2 in us-east-1. A SigV4
    # POST policy carries x-amz-algorithm; SigV2 carries AWSAccessKeyId.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    clinical_storage.get_s3_client.cache_clear()
    try:
        post = clinical_storage.create_upload_post(
            s3_key="tenants/test/files/abc/original",
            file_id="abc",
            tenant_id="test",
            content_type="application/pdf",
            size_bytes=1024,
        )
        assert post["fields"].get("x-amz-algorithm") == "AWS4-HMAC-SHA256"
        assert "AWSAccessKeyId" not in post["fields"]
        assert post["fields"]["x-amz-server-side-encryption"] == "aws:kms"
    finally:
        clinical_storage.get_s3_client.cache_clear()
