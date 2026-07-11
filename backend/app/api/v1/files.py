"""Tenant-scoped clinical file storage API."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import entitlement
from app.db.session import get_db
from app.models.clinical_file import ClinicalFile, TenantStorageUsage
from app.models.expediente import Expediente
from app.services.clinical_storage import (
    create_download_url,
    create_upload_post,
    get_scan_status,
    head_uploaded_object,
    validate_upload,
)

router = APIRouter()


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(gt=0)
    category: Literal["analysis", "xray", "prescription", "consent", "other"] = "other"


def _tenant_uuid(request: Request) -> uuid.UUID:
    try:
        return uuid.UUID(str(request.state.tenant_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=403, detail="Contexto de clínica inválido") from exc


def _quota(request: Request) -> int:
    return int(entitlement(getattr(request.state, "plan", None), "file_storage_quota_bytes") or 0)


async def _locked_usage(
    db: AsyncSession, tenant_id: uuid.UUID, quota_bytes: int
) -> TenantStorageUsage:
    await db.execute(
        insert(TenantStorageUsage)
        .values(tenant_id=tenant_id, quota_bytes=quota_bytes)
        .on_conflict_do_nothing(index_elements=[TenantStorageUsage.tenant_id])
    )
    usage = (
        await db.execute(
            select(TenantStorageUsage)
            .where(TenantStorageUsage.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one()
    usage.quota_bytes = quota_bytes

    now = datetime.now(timezone.utc)
    expired = (
        (
            await db.execute(
                select(ClinicalFile).where(
                    ClinicalFile.tenant_id == tenant_id,
                    ClinicalFile.status == "pending_upload",
                    ClinicalFile.reservation_expires_at < now,
                )
            )
        )
        .scalars()
        .all()
    )
    if expired:
        released = sum(item.size_bytes for item in expired)
        usage.reserved_bytes = max(0, usage.reserved_bytes - released)
        for item in expired:
            item.status = "expired"
    usage.updated_at = now
    return usage


def _serialize(item: ClinicalFile) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "expediente_id": str(item.expediente_id),
        "paciente_id": str(item.paciente_id),
        "filename": item.original_filename,
        "content_type": item.content_type,
        "size_bytes": item.size_bytes,
        "category": item.category,
        "status": item.status,
        "scan_status": item.scan_status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
    }


@router.get("/usage")
async def storage_usage(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _tenant_uuid(request)
    quota = _quota(request)
    usage = await _locked_usage(db, tenant_id, quota)
    consumed = usage.used_bytes + usage.reserved_bytes
    return {
        "plan": getattr(request.state, "plan", "basico"),
        "quota_bytes": quota,
        "used_bytes": usage.used_bytes,
        "reserved_bytes": usage.reserved_bytes,
        "available_bytes": max(0, quota - consumed),
        "percent_used": round((consumed / quota) * 100, 2) if quota else 0,
    }


@router.post("/expedientes/{expediente_id}/upload-url", status_code=201)
async def request_upload(
    expediente_id: uuid.UUID,
    data: UploadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _tenant_uuid(request)
    quota = _quota(request)
    if quota <= 0:
        raise HTTPException(
            status_code=403, detail="El almacenamiento de archivos requiere el plan Pro"
        )
    try:
        filename, content_type = validate_upload(data.filename, data.content_type, data.size_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    expediente = (
        await db.execute(
            select(Expediente).where(
                Expediente.id == expediente_id,
                Expediente.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not expediente:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    usage = await _locked_usage(db, tenant_id, quota)
    if usage.used_bytes + usage.reserved_bytes + data.size_bytes > quota:
        available = max(0, quota - usage.used_bytes - usage.reserved_bytes)
        raise HTTPException(
            status_code=409,
            detail={"message": "Espacio insuficiente", "available_bytes": available},
        )

    file_id = uuid.uuid4()
    s3_key = f"tenants/{tenant_id}/expedientes/{expediente.id}/files/{file_id}/original"
    item = ClinicalFile(
        id=file_id,
        tenant_id=tenant_id,
        paciente_id=expediente.paciente_id,
        expediente_id=expediente.id,
        s3_key=s3_key,
        original_filename=filename,
        content_type=content_type,
        size_bytes=data.size_bytes,
        category=data.category,
        uploaded_by=str(request.state.user_id),
        reservation_expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=settings.file_signed_url_ttl_seconds + 120),
    )
    db.add(item)
    usage.reserved_bytes += data.size_bytes
    await db.flush()

    upload = await asyncio.to_thread(
        create_upload_post,
        s3_key=s3_key,
        file_id=str(file_id),
        tenant_id=str(tenant_id),
        content_type=content_type,
        size_bytes=data.size_bytes,
    )
    return {
        "file_id": str(file_id),
        "upload_url": upload["url"],
        "upload_fields": upload["fields"],
        "expires_in": settings.file_signed_url_ttl_seconds,
    }


@router.post("/{file_id}/complete")
async def complete_upload(
    file_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    tenant_id = _tenant_uuid(request)
    usage = await _locked_usage(db, tenant_id, _quota(request))
    item = (
        await db.execute(
            select(ClinicalFile)
            .where(ClinicalFile.id == file_id, ClinicalFile.tenant_id == tenant_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if item.status != "pending_upload":
        if item.status in {"scanning", "available"}:
            return _serialize(item)
        raise HTTPException(status_code=409, detail="La reserva de carga ya no está activa")

    try:
        head = await asyncio.to_thread(head_uploaded_object, item.s3_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(
                status_code=409, detail="La carga a S3 todavía no está completa"
            ) from exc
        raise
    metadata = head.get("Metadata", {})
    if head.get("ContentLength") != item.size_bytes:
        raise HTTPException(status_code=409, detail="El tamaño cargado no coincide con la reserva")
    if metadata.get("file-id") != str(item.id) or metadata.get("tenant-id") != str(tenant_id):
        raise HTTPException(status_code=409, detail="Los metadatos del archivo no coinciden")
    if head.get("ServerSideEncryption") != "aws:kms":
        raise HTTPException(status_code=409, detail="El archivo no tiene el cifrado requerido")

    usage.reserved_bytes = max(0, usage.reserved_bytes - item.size_bytes)
    usage.used_bytes += item.size_bytes
    item.s3_version_id = head.get("VersionId")
    item.completed_at = datetime.now(timezone.utc)
    item.reservation_expires_at = None
    item.status = "scanning" if settings.malware_scan_required else "available"
    item.scan_status = "pending" if settings.malware_scan_required else "not_required"
    await db.flush()
    return _serialize(item)


@router.get("/expedientes/{expediente_id}")
async def list_files(
    expediente_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    tenant_id = _tenant_uuid(request)
    result = await db.execute(
        select(ClinicalFile)
        .where(
            ClinicalFile.tenant_id == tenant_id,
            ClinicalFile.expediente_id == expediente_id,
            ClinicalFile.deleted_at.is_(None),
            ClinicalFile.status.notin_(["expired", "pending_upload"]),
        )
        .order_by(ClinicalFile.created_at.desc())
    )
    items = list(result.scalars().all())
    scanning = [item for item in items if item.status == "scanning"]
    if scanning:
        await asyncio.gather(*(_refresh_scan(item) for item in scanning), return_exceptions=True)
        await db.flush()
    return [_serialize(item) for item in items]


async def _refresh_scan(item: ClinicalFile) -> None:
    if not settings.malware_scan_required or item.status != "scanning":
        return
    tag = await asyncio.to_thread(get_scan_status, item.s3_key, item.s3_version_id)
    if tag == "NO_THREATS_FOUND":
        item.scan_status = tag
        item.status = "available"
    elif tag == "THREATS_FOUND":
        item.scan_status = tag
        item.status = "quarantined"
    elif tag in {"UNSUPPORTED", "ACCESS_DENIED", "FAILED"}:
        item.scan_status = tag
        item.status = "scan_failed"


@router.get("/{file_id}/download-url")
async def download_url(
    file_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    tenant_id = _tenant_uuid(request)
    item = (
        await db.execute(
            select(ClinicalFile).where(
                ClinicalFile.id == file_id,
                ClinicalFile.tenant_id == tenant_id,
                ClinicalFile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        await _refresh_scan(item)
    except ClientError:
        raise HTTPException(
            status_code=503, detail="No se pudo verificar el análisis de seguridad"
        ) from None
    if item.status != "available":
        detail = "El archivo sigue en análisis de seguridad"
        if item.status == "quarantined":
            detail = "El archivo fue bloqueado por el análisis de seguridad"
        elif item.status == "scan_failed":
            detail = "El análisis de seguridad falló; el archivo permanece bloqueado"
        raise HTTPException(status_code=423, detail=detail)

    url = await asyncio.to_thread(
        create_download_url,
        s3_key=item.s3_key,
        version_id=item.s3_version_id,
        filename=item.original_filename,
        content_type=item.content_type,
    )
    return {"url": url, "expires_in": settings.file_signed_url_ttl_seconds}


@router.delete("/{file_id}", status_code=204)
async def archive_file(
    file_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    tenant_id = _tenant_uuid(request)
    item = (
        await db.execute(
            select(ClinicalFile).where(
                ClinicalFile.id == file_id,
                ClinicalFile.tenant_id == tenant_id,
                ClinicalFile.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    item.deleted_at = datetime.now(timezone.utc)
    item.status = "retained_deleted"
    # The object and its quota remain retained for the clinical record retention period.
