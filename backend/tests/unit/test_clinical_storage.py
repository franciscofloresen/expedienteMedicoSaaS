import pytest

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
