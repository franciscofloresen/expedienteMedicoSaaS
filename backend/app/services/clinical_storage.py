"""S3 signing and validation for tenant-scoped clinical files."""

from functools import lru_cache
from pathlib import PurePath
from typing import Any, cast

import boto3
from botocore.config import Config

from app.core.config import settings

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/dicom",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ALLOWED_EXTENSIONS = {".pdf", ".dcm", ".jpg", ".jpeg", ".png", ".webp"}
SCAN_TAG = "GuardDutyMalwareScanStatus"


def validate_upload(filename: str, content_type: str, size_bytes: int) -> tuple[str, str]:
    safe_name = PurePath(filename.replace("\\", "/")).name.strip()
    if not safe_name or safe_name in {".", ".."} or any(ord(c) < 32 for c in safe_name):
        raise ValueError("Nombre de archivo inválido")
    if len(safe_name.encode("utf-8")) > 255:
        raise ValueError("El nombre del archivo es demasiado largo")

    extension = PurePath(safe_name).suffix.lower()
    normalized_type = content_type.lower().strip()
    if extension == ".dcm" and normalized_type == "application/octet-stream":
        normalized_type = "application/dicom"
    if extension not in ALLOWED_EXTENSIONS or normalized_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Formato no permitido. Usa PDF, DICOM, JPG, PNG o WebP")
    if size_bytes <= 0:
        raise ValueError("El archivo está vacío")
    if size_bytes > settings.file_upload_max_bytes:
        max_mb = settings.file_upload_max_bytes // (1024 * 1024)
        raise ValueError(f"El archivo excede el máximo de {max_mb} MB")
    return safe_name, normalized_type


@lru_cache
def get_s3_client() -> Any:
    # SigV4 is mandatory: S3 rejects presigned requests that specify SSE-KMS
    # (uploads AND downloads of KMS-encrypted objects) when signed with the
    # legacy SigV2 that boto3 still defaults to for presigning in us-east-1.
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        config=Config(signature_version="s3v4"),
    )


def create_upload_post(
    *, s3_key: str, file_id: str, tenant_id: str, content_type: str, size_bytes: int
) -> dict[str, Any]:
    fields = {
        "Content-Type": content_type,
        "x-amz-server-side-encryption": "aws:kms",
        "x-amz-server-side-encryption-aws-kms-key-id": settings.kms_encryption_key_id,
        "x-amz-meta-file-id": file_id,
        "x-amz-meta-tenant-id": tenant_id,
    }
    conditions: list[Any] = [
        {"Content-Type": content_type},
        {"x-amz-server-side-encryption": "aws:kms"},
        {"x-amz-server-side-encryption-aws-kms-key-id": settings.kms_encryption_key_id},
        {"x-amz-meta-file-id": file_id},
        {"x-amz-meta-tenant-id": tenant_id},
        ["content-length-range", size_bytes, size_bytes],
    ]
    return cast(
        dict[str, Any],
        get_s3_client().generate_presigned_post(
            Bucket=settings.s3_expedientes_bucket,
            Key=s3_key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=settings.file_signed_url_ttl_seconds,
        ),
    )


def head_uploaded_object(s3_key: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        get_s3_client().head_object(
            Bucket=settings.s3_expedientes_bucket,
            Key=s3_key,
        ),
    )


def get_scan_status(s3_key: str, version_id: str | None = None) -> str | None:
    params: dict[str, str] = {
        "Bucket": settings.s3_expedientes_bucket,
        "Key": s3_key,
    }
    if version_id:
        params["VersionId"] = version_id
    response = get_s3_client().get_object_tagging(**params)
    tags = {item["Key"]: item["Value"] for item in response.get("TagSet", [])}
    return tags.get(SCAN_TAG)


def create_download_url(
    *, s3_key: str, version_id: str | None, filename: str, content_type: str
) -> str:
    params: dict[str, str] = {
        "Bucket": settings.s3_expedientes_bucket,
        "Key": s3_key,
        "ResponseContentType": content_type,
        "ResponseContentDisposition": f'attachment; filename="{filename.replace(chr(34), "")}"',
    }
    if version_id:
        params["VersionId"] = version_id
    return cast(
        str,
        get_s3_client().generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=settings.file_signed_url_ttl_seconds,
        ),
    )
