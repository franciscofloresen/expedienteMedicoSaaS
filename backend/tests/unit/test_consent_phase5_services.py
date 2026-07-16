import base64
import uuid
from datetime import date, datetime, timezone

import pytest

from app.models.consentimiento import Consentimiento
from app.models.consentimiento_evidencia import ConsentimientoFirmante
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.services.consent_documents import build_final_consent_pdf, store_final_consent_pdf
from app.services.consent_signatures import normalize_signature

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z3ZkAAAAASUVORK5CYII="
)
_PNG_URL = f"data:image/png;base64,{base64.b64encode(_PNG).decode()}"


def test_signature_normalization_is_stable_and_size_limited() -> None:
    normalized = normalize_signature(_PNG_URL)
    assert normalized.media_type in {"image/jpeg", None}
    assert normalize_signature(normalized.data_url).sha256 == normalized.sha256

    with pytest.raises(ValueError, match="base64"):
        normalize_signature("not-base64")
    with pytest.raises(ValueError, match="512 KB"):
        normalize_signature(base64.b64encode(b"x" * (512 * 1024 + 1)).decode())


def test_final_pdf_and_storage_key_are_deterministic() -> None:
    tenant_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    expediente_id = uuid.uuid4()
    consent_id = uuid.uuid4()
    signed_at = datetime.now(timezone.utc)
    consentimiento = Consentimiento(
        id=consent_id,
        tenant_id=tenant_id,
        paciente_id=patient_id,
        expediente_id=expediente_id,
        template_key="general_atencion",
        version="1.0",
        procedimiento="Valoración",
        contenido_renderizado="Contenido final con acentos: atención médica.",
        medico_nombre="Dra. Prueba",
        medico_cedula="12345",
        medico_especialidad="General",
        firmado_medico_en=signed_at,
        hash_contenido="a" * 64,
    )
    paciente = Paciente(
        id=patient_id,
        tenant_id=tenant_id,
        nombre_completo="Paciente Prueba",
        fecha_nacimiento=date(1990, 1, 1),
        sexo="X",
    )
    expediente = Expediente(
        id=expediente_id,
        tenant_id=tenant_id,
        paciente_id=patient_id,
        folio="EXP-TEST",
        creado_por=tenant_id,
    )
    normalized = normalize_signature(_PNG_URL)
    firmante = ConsentimientoFirmante(
        tenant_id=tenant_id,
        consentimiento_id=consent_id,
        tipo="paciente",
        orden=0,
        nombre="Paciente Prueba",
        firma_base64=normalized.data_url,
        firma_sha256=normalized.sha256,
        firmado_en=signed_at,
    )
    pdf = build_final_consent_pdf(
        consentimiento=consentimiento,
        paciente=paciente,
        expediente=expediente,
        firmantes=[firmante],
        verification_url="https://example.test/verify/token",
    )
    assert pdf.startswith(b"%PDF-")
    stored = store_final_consent_pdf(
        tenant_id=str(tenant_id), consentimiento_id=str(consent_id), pdf_bytes=pdf
    )
    assert stored.key == f"tenants/{tenant_id}/consentimientos/{consent_id}/final.pdf"
    assert stored.size_bytes == len(pdf)
    assert len(stored.sha256) == 64
