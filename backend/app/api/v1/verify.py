from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.verification_token import VerificationToken

router = APIRouter()


@router.get("/{token}")
async def verify_document(token: str, db: AsyncSession = Depends(get_db)) -> Any:
    verification = (
        await db.execute(
            select(VerificationToken).where(VerificationToken.token == token)
        )
    ).scalar_one_or_none()
    if not verification:
        return {
            "status": "not_found",
            "valid": False,
            "message": "Documento no encontrado o token inválido.",
        }
    if verification.status != "active":
        return {
            "status": "revoked",
            "valid": False,
            "message": "Este documento fue revocado.",
            "resource_type": verification.resource_type,
        }

    metadata = verification.public_metadata or {}
    return {
        "status": "active",
        "valid": True,
        "resource_type": verification.resource_type,
        "folio": metadata.get("folio") or f"{verification.resource_type.upper()}-{str(verification.resource_id)[:8].upper()}",
        "medico_nombre": metadata.get("medico_nombre"),
        "medico_cedula": metadata.get("medico_cedula"),
        "fecha_emision": metadata.get("fecha_emision"),
        "hash": metadata.get("hash"),
        "privacy_notice": (
            "Esta verificación solo muestra metadatos mínimos del documento. "
            "No expone contenido clínico, diagnósticos, medicamentos ni datos personales sensibles."
        ),
    }
