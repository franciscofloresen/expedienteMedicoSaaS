from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.consentimiento import Consentimiento
from app.models.consentimiento_evidencia import (
    ConsentimientoDocumentoFinal,
    ConsentimientoFirmante,
    ConsentimientoRevocacion,
)
from app.models.verification_token import VerificationToken
from app.services.consent_signatures import (
    canonical_consent_content,
    consent_signing_metadata,
)
from app.services.firma import verify_signature

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
        revoked_at = verification.revoked_at
        if verification.resource_type == "consentimiento":
            revocation = (
                await db.execute(
                    select(ConsentimientoRevocacion).where(
                        ConsentimientoRevocacion.consentimiento_id == verification.resource_id
                    )
                )
            ).scalar_one_or_none()
            if revocation is not None:
                revoked_at = revocation.revocado_en
        return {
            "status": "revoked",
            "valid": False,
            "message": "Este documento fue revocado.",
            "resource_type": verification.resource_type,
            "revoked_at": revoked_at.isoformat() if revoked_at else None,
        }

    metadata = verification.public_metadata or {}
    payload = {
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
    if verification.resource_type != "consentimiento":
        return payload

    consentimiento = (
        await db.execute(
            select(Consentimiento).where(Consentimiento.id == verification.resource_id)
        )
    ).scalar_one_or_none()
    documento = (
        await db.execute(
            select(ConsentimientoDocumentoFinal).where(
                ConsentimientoDocumentoFinal.consentimiento_id == verification.resource_id
            )
        )
    ).scalar_one_or_none()
    if consentimiento is None:
        return {
            **payload,
            "status": "invalid",
            "valid": False,
            "message": "El token no tiene un consentimiento asociado.",
        }

    # Pre-Fase-5 signed documents remain publicly verifiable by their original token
    # metadata. New documents additionally prove the KMS signature and final S3 record.
    if not consentimiento.firma_kms_key_id:
        payload["verification_level"] = "legacy_metadata"
        payload["final_document"] = False
        return payload

    firmantes = list(
        (
            await db.execute(
                select(ConsentimientoFirmante)
                .where(ConsentimientoFirmante.consentimiento_id == consentimiento.id)
                .order_by(ConsentimientoFirmante.tipo, ConsentimientoFirmante.orden)
            )
        ).scalars().all()
    )
    signature_valid = bool(
        consentimiento.firma_digital
        and consentimiento.hash_contenido
        and verify_signature(
            content=canonical_consent_content(consentimiento, firmantes),
            metadata=consent_signing_metadata(consentimiento),
            signature=consentimiento.firma_digital,
            stored_hash=consentimiento.hash_contenido,
            key_id=consentimiento.firma_kms_key_id,
        )
    )
    payload.update(
        {
            "valid": signature_valid and documento is not None,
            "status": "active" if signature_valid and documento is not None else "invalid",
            "verification_level": "kms_signature_and_final_document",
            "final_document": documento is not None,
            "final_document_sha256": documento.contenido_sha256 if documento else None,
            "firma_algoritmo": consentimiento.firma_algoritmo,
        }
    )
    if not payload["valid"]:
        payload["message"] = "La evidencia criptográfica o el documento final no es válida."
    return payload
