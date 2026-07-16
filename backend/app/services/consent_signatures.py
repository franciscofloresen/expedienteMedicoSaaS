"""Normalization and canonicalization for consent human signatures."""

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image as PILImage

from app.models.consentimiento import Consentimiento
from app.models.consentimiento_evidencia import ConsentimientoFirmante

_DATA_URL = re.compile(
    r"^data:(image/(?:png|jpeg)|application/octet-stream);base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_MAX_SIGNATURE_BYTES = 512 * 1024


@dataclass(frozen=True)
class NormalizedSignature:
    data_url: str
    content: bytes
    media_type: str | None
    sha256: str


def normalize_signature(value: str) -> NormalizedSignature:
    """Validate, size-limit and canonicalize a handwritten-signature payload.

    New clients send a compressed PNG/JPEG data URL. A raw base64 compatibility path
    remains for previously deployed clients, but only real image data is embedded in
    the final PDF. Every accepted payload is sealed by SHA-256 in the signed content.
    """
    compact = "".join(value.split())
    match = _DATA_URL.fullmatch(compact)
    declared_type = match.group(1).lower() if match else None
    media_type = declared_type if declared_type and declared_type.startswith("image/") else None
    encoded = match.group(2) if match else compact
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("La firma no contiene base64 válido") from exc
    if not content:
        raise ValueError("La firma está vacía")
    if len(content) > _MAX_SIGNATURE_BYTES:
        raise ValueError("La firma excede 512 KB; vuelve a capturarla")
    if media_type:
        try:
            with PILImage.open(BytesIO(content)) as source:
                source.load()
                source.thumbnail((1200, 400))
                image = PILImage.new("RGB", source.size, "white")
                if "A" in source.getbands():
                    image.paste(source, mask=source.getchannel("A"))
                else:
                    image.paste(source.convert("RGB"))
                compressed = BytesIO()
                image.save(compressed, format="JPEG", quality=75, optimize=True)
                content = compressed.getvalue()
                media_type = "image/jpeg"
        except Exception:
            # Keep the original beta's pseudo-image payload compatible: it was already
            # accepted in production and remains hashable, but is not embedded.
            media_type = None
    canonical_type = media_type or "application/octet-stream"
    canonical = f"data:{canonical_type};base64,{base64.b64encode(content).decode('ascii')}"
    return NormalizedSignature(
        data_url=canonical,
        content=content,
        media_type=media_type,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def canonical_consent_content(
    consentimiento: Consentimiento,
    firmantes: list[ConsentimientoFirmante],
) -> str:
    """Return the immutable clinical content sealed by the doctor's KMS signature."""
    signers: list[dict[str, Any]] = []
    for signer in sorted(firmantes, key=lambda item: (item.tipo == "testigo", item.orden)):
        signers.append(
            {
                "tipo": signer.tipo,
                "orden": signer.orden,
                "nombre": signer.nombre,
                "relacion_paciente": signer.relacion_paciente,
                "motivo_representacion": signer.motivo_representacion,
                "firma_sha256": signer.firma_sha256,
                "firmado_en": signer.firmado_en.isoformat(),
            }
        )
    return json.dumps(
        {
            "id": str(consentimiento.id),
            "tenant_id": str(consentimiento.tenant_id),
            "paciente_id": str(consentimiento.paciente_id),
            "expediente_id": str(consentimiento.expediente_id),
            "template_key": consentimiento.template_key,
            "version": consentimiento.version,
            "plantilla_version_id": (
                str(consentimiento.plantilla_version_id)
                if consentimiento.plantilla_version_id
                else None
            ),
            "procedimiento": consentimiento.procedimiento,
            "riesgos_principales": consentimiento.riesgos_principales,
            "contenido_renderizado": consentimiento.contenido_renderizado,
            "firmantes": signers,
            "medico_id": str(consentimiento.medico_id) if consentimiento.medico_id else None,
            "credencial_id": (
                str(consentimiento.credencial_id) if consentimiento.credencial_id else None
            ),
            "medico_nombre": consentimiento.medico_nombre,
            "medico_cedula": consentimiento.medico_cedula,
            "medico_especialidad": consentimiento.medico_especialidad,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def consent_signing_metadata(consentimiento: Consentimiento) -> dict[str, str]:
    if not consentimiento.firmado_medico_en:
        raise ValueError("El consentimiento no tiene fecha de firma médica")
    return {
        "tenant_id": str(consentimiento.tenant_id),
        "nota_id": str(consentimiento.id),
        "medico_nombre": consentimiento.medico_nombre or "",
        "medico_cedula": consentimiento.medico_cedula or "",
        "medico_especialidad": consentimiento.medico_especialidad or "General",
        "timestamp": consentimiento.firmado_medico_en.isoformat(),
    }
