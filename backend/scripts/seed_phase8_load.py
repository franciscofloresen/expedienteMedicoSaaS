"""Populate a dedicated local ``*_phase8`` database with synthetic load data.

The script refuses production and any database whose name does not end in
``_phase8``. It is idempotent and never deletes clinical rows (the same
immutability rules as production remain active).
"""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_database_url, settings

_TENANT_ID = "f8000000-0000-4000-8000-000000000008"


def _assert_safe_target(database_url: str) -> None:
    database = make_url(database_url).database or ""
    if settings.environment == "prod" or not database.endswith("_phase8"):
        raise ValueError("synthetic seed requires development and a database ending in _phase8")


async def seed(args: argparse.Namespace) -> dict[str, object]:
    if settings.environment == "prod":
        raise ValueError("synthetic seed is disabled in production")
    database_url = get_database_url()
    _assert_safe_target(database_url)
    engine = create_async_engine(database_url, pool_size=1, max_overflow=0)
    async with engine.begin() as connection:
        cie10_count = (
            await connection.execute(text("SELECT count(*) FROM cie10 WHERE active AND selectable"))
        ).scalar_one()
        if cie10_count < 10000:
            raise ValueError("import the complete CIE-10 catalog before seeding Fase 8")

        await connection.execute(
            text(
                """
                INSERT INTO tenants
                  (id, clerk_id, nombre_medico, cedula, especialidad, email, plan, activo)
                VALUES
                  (CAST(:tenant_id AS uuid), 'phase8-local', 'Dra. Carga Sintética',
                   'FASE8-LOCAL', 'Medicina de prueba', 'phase8@local.invalid', 'pro', true)
                ON CONFLICT DO NOTHING
                """
            ),
            {"tenant_id": _TENANT_ID},
        )
        await connection.execute(
            text(
                """
                INSERT INTO pacientes
                  (id, tenant_id, nombre_completo, fecha_nacimiento, sexo, curp,
                   telefono, activo, creado_por)
                SELECT md5('phase8-patient-' || g)::uuid, CAST(:tenant_id AS uuid),
                       'Paciente Sintético ' || lpad(g::text, 6, '0'), DATE '1980-01-01',
                       CASE WHEN g % 2 = 0 THEN 'F' ELSE 'M' END,
                       'P8' || lpad(g::text, 16, '0'),
                       '555' || lpad(g::text, 7, '0'), true, CAST(:tenant_id AS uuid)
                FROM generate_series(1, :patients) AS g
                ON CONFLICT DO NOTHING
                """
            ),
            {"tenant_id": _TENANT_ID, "patients": args.patients},
        )
        await connection.execute(
            text(
                """
                INSERT INTO expedientes (id, tenant_id, paciente_id, folio, estado, creado_por)
                SELECT md5('phase8-record-' || g)::uuid, CAST(:tenant_id AS uuid),
                       md5('phase8-patient-' || g)::uuid,
                       'P8-' || lpad(g::text, 12, '0'), 'activo', CAST(:tenant_id AS uuid)
                FROM generate_series(1, :patients) AS g
                ON CONFLICT DO NOTHING
                """
            ),
            {"tenant_id": _TENANT_ID, "patients": args.patients},
        )
        await connection.execute(
            text(
                """
                INSERT INTO notas
                  (id, expediente_id, tenant_id, tipo_nota, contenido, estado,
                   es_editable, creado_por, creado_en)
                SELECT md5('phase8-note-' || p || '-' || n)::uuid,
                       md5('phase8-record-' || p)::uuid, CAST(:tenant_id AS uuid),
                       'evolucion',
                       jsonb_build_object(
                         'motivo', 'Seguimiento sintético sin PHI',
                         'texto', repeat('evolución clínica simulada ', 20)
                       )::text,
                       'draft', true, CAST(:tenant_id AS uuid),
                       now() - make_interval(days => (:notes_per_patient - n))
                FROM generate_series(1, :patients) AS p
                CROSS JOIN generate_series(1, :notes_per_patient) AS n
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "tenant_id": _TENANT_ID,
                "patients": args.patients,
                "notes_per_patient": args.notes_per_patient,
            },
        )
        await connection.execute(
            text(
                """
                WITH catalog AS (
                  SELECT array_agg(code ORDER BY code) AS codes
                  FROM (SELECT code FROM cie10 WHERE active AND selectable ORDER BY code LIMIT 500) c
                )
                INSERT INTO nota_diagnosticos
                  (id, tenant_id, nota_id, cie10_code, orden, es_principal, certeza,
                   descripcion_snapshot, version_snapshot, creado_por)
                SELECT md5('phase8-dx-' || p || '-' || n || '-' || d)::uuid,
                       CAST(:tenant_id AS uuid), md5('phase8-note-' || p || '-' || n)::uuid,
                       catalog.codes[1 + ((p + n + d) % array_length(catalog.codes, 1))],
                       d - 1, d = 1, 'confirmado', 'Diagnóstico sintético', 'CIE-10-MX',
                       CAST(:tenant_id AS uuid)
                FROM generate_series(1, :patients) AS p
                CROSS JOIN generate_series(1, :notes_per_patient) AS n
                CROSS JOIN generate_series(1, :diagnoses_per_note) AS d
                CROSS JOIN catalog
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "tenant_id": _TENANT_ID,
                "patients": args.patients,
                "notes_per_patient": args.notes_per_patient,
                "diagnoses_per_note": args.diagnoses_per_note,
            },
        )
        await connection.execute(
            text(
                """
                INSERT INTO consentimientos
                  (id, tenant_id, paciente_id, expediente_id, template_key, version,
                   procedimiento, contenido_renderizado, status, created_at)
                SELECT md5('phase8-consent-' || p || '-' || c)::uuid,
                       CAST(:tenant_id AS uuid), md5('phase8-patient-' || p)::uuid,
                       md5('phase8-record-' || p)::uuid, 'consentimiento_general', '1.0',
                       'Procedimiento sintético', repeat('contenido legal simulado ', 30),
                       'draft', now() - make_interval(days => c)
                FROM generate_series(1, :patients) AS p
                CROSS JOIN generate_series(1, :consents_per_patient) AS c
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "tenant_id": _TENANT_ID,
                "patients": args.patients,
                "consents_per_patient": args.consents_per_patient,
            },
        )
        counts = (
            await connection.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM pacientes WHERE tenant_id=CAST(:tenant_id AS uuid)),
                      (SELECT count(*) FROM notas WHERE tenant_id=CAST(:tenant_id AS uuid)),
                      (SELECT count(*) FROM nota_diagnosticos WHERE tenant_id=CAST(:tenant_id AS uuid)),
                      (SELECT count(*) FROM consentimientos WHERE tenant_id=CAST(:tenant_id AS uuid))
                    """
                ),
                {"tenant_id": _TENANT_ID},
            )
        ).one()
        sample_expediente = (
            await connection.execute(
                text(
                    "SELECT id::text FROM expedientes WHERE tenant_id=CAST(:tenant_id AS uuid) "
                    "ORDER BY folio LIMIT 1"
                ),
                {"tenant_id": _TENANT_ID},
            )
        ).scalar_one()
    await engine.dispose()
    return {
        "tenant_id": _TENANT_ID,
        "sample_expediente_id": sample_expediente,
        "counts": {
            "patients": counts[0],
            "notes": counts[1],
            "diagnoses": counts[2],
            "consents": counts[3],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patients", type=int, default=2_000)
    parser.add_argument("--notes-per-patient", type=int, default=50)
    parser.add_argument("--diagnoses-per-note", type=int, default=3)
    parser.add_argument("--consents-per-patient", type=int, default=5)
    args = parser.parse_args()
    for value in vars(args).values():
        if value < 1:
            parser.error("all scale values must be positive")
    return args


def main() -> int:
    try:
        result = asyncio.run(seed(parse_args()))
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
