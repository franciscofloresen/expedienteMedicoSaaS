"""Integration tests for «Descargar todo» (Entregable 1 — plan de pre-venta).

Covers: full export of a record with signed note + receta + consentimiento +
archivo, tenant isolation (404), quarantined files listed without URL, the
absence of a plan gate (Básico can export), the reauthentication dependency,
the audit-log entry, and the formato_version contract.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.services.exportacion as exportacion_service
from app.api.v1 import files as files_api
from app.api.v1.exportacion import exportar_expediente, exportar_indice_consultorio
from app.core.config import settings
from app.core.security import require_reauthentication
from app.db.session import _get_session_factory
from app.main import app
from app.models.consentimiento import Consentimiento
from app.models.consentimiento_evidencia import ConsentimientoFirmante
from tests.conftest import TENANT_A_ID, TENANT_B_ID, use_migrations

pytestmark = pytest.mark.asyncio

HEADERS_A = {"X-Tenant-ID": TENANT_A_ID}
HEADERS_B = {"X-Tenant-ID": TENANT_B_ID}

# Patients created here use CURP prefix EXPO9001. In create_all mode the test DB
# is session-scoped, so this suite deletes its own rows — otherwise the tenant A
# expedientes accumulate and trip the basico max_expedientes=5 limit in later
# plan-limited suites (see test_fotografias for the same pattern), and the file
# uploads inflate tenant_storage_usage for test_files.
_CURP_PREFIX = "EXPO9001"


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_created_rows(setup_database):
    yield
    if use_migrations():
        return
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "DELETE FROM recetas WHERE nota_id IN (SELECT id FROM notas "
                "WHERE expediente_id IN (SELECT id FROM expedientes WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%')))"
            )
        )
        await conn.execute(
            text(
                "UPDATE tenant_storage_usage SET used_bytes = GREATEST(used_bytes - COALESCE("
                "(SELECT SUM(size_bytes) FROM clinical_files WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%')"
                " AND status NOT IN ('pending_upload', 'expired')), 0), 0) "
                "WHERE tenant_id = :tenant_id"
            ),
            {"tenant_id": TENANT_A_ID},
        )
        await conn.execute(
            text(
                "DELETE FROM consentimiento_firmantes WHERE consentimiento_id IN "
                "(SELECT id FROM consentimientos WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%'))"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM consentimientos WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%')"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM fotografias_clinicas WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%')"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM clinical_files WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%')"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM notas WHERE expediente_id IN "
                "(SELECT id FROM expedientes WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%'))"
            )
        )
        await conn.execute(
            text(
                "DELETE FROM expedientes WHERE paciente_id IN "
                "(SELECT id FROM pacientes WHERE curp LIKE 'EXPO9001%')"
            )
        )
        await conn.execute(text("DELETE FROM pacientes WHERE curp LIKE 'EXPO9001%'"))
    await engine.dispose()


def _curp() -> str:
    # Must satisfy the CURP pattern ^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z\d]\d$ and keep
    # the EXPO9001 prefix the cleanup fixture filters on.
    seed = uuid.uuid4().hex
    letters = "".join("ABCDEFGHIJKLMNOP"[int(char, 16)] for char in seed[:5])
    return f"EXPO900101M{letters}0{int(seed[5], 16) % 10}"


async def _seed_record_via_api(client: AsyncClient, *, nombre: str) -> tuple[str, str]:
    """Create paciente + expediente through the API (tenant A). Returns ids.

    Creation runs as Pro so this suite never pollutes the shared tenant into the
    Básico 5-expediente limit (see test_fotografias); the export reads themselves
    are exercised without X-Plan.
    """
    headers_pro = {**HEADERS_A, "X-Plan": "pro"}
    patient = await client.post(
        "/api/v1/pacientes/",
        headers=headers_pro,
        json={
            "nombre_completo": nombre,
            "sexo": "F",
            "fecha_nacimiento": "1988-05-05",
            "curp": _curp(),
            "telefono": "312-000-0000",
        },
    )
    assert patient.status_code == 201
    paciente_id = patient.json()["id"]
    expediente = await client.post(
        "/api/v1/expedientes/",
        headers=headers_pro,
        json={"paciente_id": paciente_id, "antecedentes": "Sin antecedentes relevantes"},
    )
    assert expediente.status_code == 201
    return paciente_id, expediente.json()["id"]


async def _seed_signed_nota(client: AsyncClient, expediente_id: str) -> str:
    nota = await client.post(
        "/api/v1/notas/",
        headers=HEADERS_A,
        json={
            "expediente_id": expediente_id,
            "tipo_nota": "evolucion",
            "contenido": {"evolucion_y_actualizacion_cuadro": "Evolución favorable."},
            "signos_vitales": {"frecuencia_cardiaca": 70},
            "diagnosticos": ["Dermatitis"],
            "tratamiento": "Emolientes",
        },
    )
    assert nota.status_code == 201
    nota_id = nota.json()["id"]
    firmada = await client.post(f"/api/v1/notas/{nota_id}/firmar", headers=HEADERS_A)
    assert firmada.status_code == 200
    return nota_id


async def _seed_consentimiento(paciente_id: str, expediente_id: str) -> str:
    """Insert a signed consentimiento + one firmante directly (bypass-RLS engine)."""
    consent_id = uuid.uuid4()
    factory = _get_session_factory()
    async with factory() as session, session.begin():
        session.add(
            Consentimiento(
                id=consent_id,
                tenant_id=uuid.UUID(TENANT_A_ID),
                paciente_id=uuid.UUID(paciente_id),
                expediente_id=uuid.UUID(expediente_id),
                template_key="derm_prueba",
                version="1.0",
                procedimiento="Peeling químico",
                contenido_renderizado="Contenido del consentimiento renderizado",
                status="signed",
                hash_contenido="a" * 64,
                firma_algoritmo="ECDSA_SHA_256",
                firmado_paciente_nombre="Paciente Export",
                firmado_paciente_en=datetime.now(timezone.utc),
                firmado_medico_en=datetime.now(timezone.utc),
            )
        )
        session.add(
            ConsentimientoFirmante(
                tenant_id=uuid.UUID(TENANT_A_ID),
                consentimiento_id=consent_id,
                tipo="paciente",
                orden=0,
                nombre="Paciente Export",
                firma_base64="data:image/png;base64,AAAA",
                firma_sha256="b" * 64,
            )
        )
    return str(consent_id)


async def _seed_file(
    client: AsyncClient, expediente_id: str, monkeypatch, *, quarantined: bool
) -> str:
    """Upload a file through the API; optionally drive it to `quarantined`."""
    headers = {**HEADERS_A, "X-Plan": "pro"}
    monkeypatch.setattr(
        files_api,
        "create_upload_post",
        lambda **_: {"url": "https://s3.example/upload", "fields": {}},
    )
    upload = await client.post(
        f"/api/v1/files/expedientes/{expediente_id}/upload-url",
        headers=headers,
        json={
            "filename": "resultado.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
            "category": "analysis",
        },
    )
    assert upload.status_code == 201
    file_id = upload.json()["file_id"]

    monkeypatch.setattr(
        files_api,
        "head_uploaded_object",
        lambda s3_key: {
            "ContentLength": 1024,
            "ServerSideEncryption": "aws:kms",
            "VersionId": "v1",
            "Metadata": {"file-id": file_id, "tenant-id": TENANT_A_ID},
        },
    )
    monkeypatch.setattr(settings, "malware_scan_required", quarantined)
    completed = await client.post(f"/api/v1/files/{file_id}/complete", headers=headers)
    assert completed.status_code == 200

    if quarantined:
        monkeypatch.setattr(files_api, "get_scan_status", lambda *_: "THREATS_FOUND")
        refreshed = await client.get(
            f"/api/v1/files/expedientes/{expediente_id}", headers=headers
        )
        statuses = {item["id"]: item["status"] for item in refreshed.json()}
        assert statuses[file_id] == "quarantined"
    return file_id


async def test_export_completo_con_todo_el_contenido(
    client: AsyncClient, seed_tenant_a, monkeypatch
):
    paciente_id, expediente_id = await _seed_record_via_api(
        client, nombre="Paciente Export Completo"
    )
    nota_id = await _seed_signed_nota(client, expediente_id)

    receta = await client.post(
        "/api/v1/recetas",
        headers=HEADERS_A,
        json={
            "nota_id": nota_id,
            "medicamentos": [{"nombre": "Paracetamol", "dosis": "500mg"}],
            "indicaciones_generales": "Cada 8 horas",
        },
    )
    assert receta.status_code in (200, 201)

    consent_id = await _seed_consentimiento(paciente_id, expediente_id)
    file_id = await _seed_file(client, expediente_id, monkeypatch, quarantined=False)

    monkeypatch.setattr(
        exportacion_service,
        "create_download_url",
        lambda **kwargs: f"https://s3.example/download/{kwargs['s3_key']}",
    )

    res = await client.get(
        f"/api/v1/expedientes/{expediente_id}/exportacion", headers=HEADERS_A
    )
    assert res.status_code == 200
    assert "attachment" in res.headers.get("content-disposition", "")
    doc = res.json()

    # formato_version is a contract from day one.
    assert doc["formato_version"] == "1.0"
    assert doc["consultorio"]["nombre_medico"] == "Dr. Tenant A"
    assert doc["paciente"]["nombre_completo"] == "Paciente Export Completo"
    assert doc["expediente"]["antecedentes"] == "Sin antecedentes relevantes"

    # Signed note: hash + algorithm exported, never the raw signature bytes.
    assert len(doc["notas"]) == 1
    nota = doc["notas"][0]
    assert nota["id"] == nota_id
    assert nota["firma"]["firmado"] is True
    assert nota["firma"]["hash_contenido"]
    assert "firma_digital" not in nota

    assert len(doc["recetas"]) == 1
    assert doc["recetas"][0]["medicamentos"][0]["nombre"] == "Paracetamol"

    assert len(doc["consentimientos"]) == 1
    consent = doc["consentimientos"][0]
    assert consent["id"] == consent_id
    assert consent["firmantes"][0]["nombre"] == "Paciente Export"
    # The signature stroke image never travels in the JSON export.
    assert "firma_base64" not in consent["firmantes"][0]

    assert len(doc["archivos"]) == 1
    archivo = doc["archivos"][0]
    assert archivo["id"] == file_id
    assert archivo["estado"] == "available"
    assert archivo["url"].startswith("https://s3.example/download/")
    assert archivo["url_expira_en"] == settings.file_signed_url_ttl_seconds


async def test_export_aislamiento_tenant_b_recibe_404(client: AsyncClient, seed_tenant_a):
    _, expediente_id = await _seed_record_via_api(client, nombre="Paciente Aislado")
    res = await client.get(
        f"/api/v1/expedientes/{expediente_id}/exportacion", headers=HEADERS_B
    )
    assert res.status_code == 404


async def test_export_archivo_en_cuarentena_sin_url(
    client: AsyncClient, seed_tenant_a, monkeypatch
):
    _, expediente_id = await _seed_record_via_api(client, nombre="Paciente Cuarentena")
    file_id = await _seed_file(client, expediente_id, monkeypatch, quarantined=True)

    def _never_called(**_):
        raise AssertionError("Nunca se genera URL para un archivo bloqueado")

    monkeypatch.setattr(exportacion_service, "create_download_url", _never_called)

    res = await client.get(
        f"/api/v1/expedientes/{expediente_id}/exportacion", headers=HEADERS_A
    )
    assert res.status_code == 200
    archivos = {item["id"]: item for item in res.json()["archivos"]}
    assert archivos[file_id]["estado"] == "quarantined"
    assert archivos[file_id]["url"] is None


async def test_export_disponible_para_plan_basico(client: AsyncClient, seed_tenant_a):
    """Portability is a right, not a Pro feature — no plan gate (regression)."""
    _, expediente_id = await _seed_record_via_api(client, nombre="Paciente Basico")
    # HEADERS_A carries no X-Plan → the tenant resolves to plan basico.
    res = await client.get(
        f"/api/v1/expedientes/{expediente_id}/exportacion", headers=HEADERS_A
    )
    assert res.status_code == 200
    index = await client.get("/api/v1/exportacion/consultorio", headers=HEADERS_A)
    assert index.status_code == 200


async def test_export_exige_reautenticacion():
    """Both endpoints declare the step-up reauthentication dependency (the check
    itself is env-gated off under testing, so we assert the wiring)."""
    for route in app.routes:
        if getattr(route, "endpoint", None) in (
            exportar_expediente,
            exportar_indice_consultorio,
        ):
            deps = [d.call for d in route.dependant.dependencies]
            assert require_reauthentication in deps, route.path


async def test_export_escribe_bitacora(client: AsyncClient, seed_tenant_a):
    headers_pro = {**HEADERS_A, "X-Plan": "pro"}
    _, expediente_id = await _seed_record_via_api(client, nombre="Paciente Bitacora")

    res = await client.get(
        f"/api/v1/expedientes/{expediente_id}/exportacion", headers=HEADERS_A
    )
    assert res.status_code == 200
    res = await client.get("/api/v1/exportacion/consultorio", headers=HEADERS_A)
    assert res.status_code == 200

    audit = await client.get("/api/v1/audit/?limit=200", headers=headers_pro)
    assert audit.status_code == 200
    actions = [entry["action"] for entry in audit.json()]
    assert f"GET /api/v1/expedientes/{expediente_id}/exportacion" in actions
    assert "GET /api/v1/exportacion/consultorio" in actions


async def test_indice_consultorio_lista_y_conteos(client: AsyncClient, seed_tenant_a):
    paciente_id, expediente_id = await _seed_record_via_api(
        client, nombre="Paciente Indice"
    )
    await _seed_signed_nota(client, expediente_id)

    res = await client.get("/api/v1/exportacion/consultorio", headers=HEADERS_A)
    assert res.status_code == 200
    doc = res.json()
    assert doc["formato_version"] == "1.0"
    entry = next(p for p in doc["pacientes"] if p["expediente_id"] == expediente_id)
    assert entry["paciente_id"] == paciente_id
    assert entry["conteos"]["notas"] == 1
    assert entry["exportacion_url"].endswith(f"/expedientes/{expediente_id}/exportacion")

    # The index never carries clinical content — only names, folios and counts.
    assert "notas" not in entry
    assert "contenido" not in str(doc["pacientes"])
