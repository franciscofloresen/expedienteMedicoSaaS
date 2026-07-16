"""Fase 3: CIE-10 catalog + nota_diagnosticos against the REAL migrated schema.

These assertions depend on the migration's RLS policies, the ``pg_trgm`` GIN index, the
partial unique index ``uq_nota_diagnostico_principal``, REVOKE DELETE and the
delete-protection trigger — none of which create_all emits — so the module runs only in
migration mode (TEST_SCHEMA_MODE=migrations), the same path CI's migration job and the
production ops-verify workflow exercise.

The catalog is loaded once via the real idempotent importer (``run_import``), which also
serves as the importer idempotency test (dry-run after apply → zero inserts).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.v1.cie10 import _search_by_code, _search_by_description
from scripts.extract_legacy_diagnosticos import run_extraction
from scripts.import_cie10 import run_import
from scripts.verify_registry import verify_cie10
from tests.conftest import TENANT_A_ID, TENANT_B_ID, _get_test_engine, use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(
        not use_migrations(),
        reason="cie10/nota_diagnosticos RLS/trigram/triggers require the migrated schema",
    ),
]


def _app_session_factory():
    return async_sessionmaker(_get_test_engine(), class_=AsyncSession, expire_on_commit=False)


async def _as_app_role(session: AsyncSession, tenant_id: str) -> None:
    """Demote to the non-superuser app role and pin the tenant, so RLS actually bites."""
    await session.execute(text("SET LOCAL ROLE medrecord_app"))
    await session.execute(
        text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id}
    )


@pytest.fixture
async def cie10_catalog(setup_database):
    """Ensure the CIE-10 catalog is loaded once (via the real importer). Cheap on reuse:
    subsequent tests just see a populated table."""
    engine = _get_test_engine()
    async with engine.begin() as conn:
        n = (await conn.execute(text("SELECT count(*) FROM cie10"))).scalar_one()
    if n < 10000:
        result = await run_import("apply")
        assert result["ok"], result


async def _seed_paciente_expediente_nota(tenant_id: str) -> tuple[str, str, str]:
    """Create a fresh paciente + expediente + a draft nota for a tenant on the bypass-RLS
    seed connection. Returns (paciente_id, expediente_id, nota_id). Random ids per call so
    committed (undeletable) rows never collide across tests or re-runs."""
    engine = _get_test_engine()
    paciente_id = str(uuid.uuid4())
    expediente_id = str(uuid.uuid4())
    nota_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex[:8]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO pacientes (id, tenant_id, nombre_completo, fecha_nacimiento, sexo) "
                "VALUES (:id, :t, 'Paciente Diagnostico', '1990-01-01', 'X')"
            ),
            {"id": paciente_id, "t": tenant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO expedientes (id, tenant_id, paciente_id, folio, creado_por) "
                "VALUES (:id, :t, :p, :folio, :t)"
            ),
            {"id": expediente_id, "t": tenant_id, "p": paciente_id, "folio": f"DX-{suffix}"},
        )
        await conn.execute(
            text(
                "INSERT INTO notas (id, tenant_id, expediente_id, tipo_nota, contenido) "
                "VALUES (:id, :t, :e, 'interconsulta', '{}')"
            ),
            {"id": nota_id, "t": tenant_id, "e": expediente_id},
        )
    return paciente_id, expediente_id, nota_id


async def _insert_diagnostico(
    conn, *, tenant_id: str, nota_id: str, code: str, es_principal: bool
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO nota_diagnosticos
                (tenant_id, nota_id, cie10_code, orden, es_principal, certeza)
            VALUES (:t, :n, :c, 0, :p, 'presuntivo')
            """
        ),
        {"t": tenant_id, "n": nota_id, "c": code, "p": es_principal},
    )


# ── Importer + verifier ──────────────────────────────────────────────────────────────


async def test_import_cie10_is_idempotent(cie10_catalog) -> None:
    """After the catalog is loaded, a dry-run reports zero would-inserts (idempotent)."""
    dry = await run_import("dry-run")
    assert dry["ok"], dry
    assert dry["counts"]["would_insert"] == 0, dry
    assert dry["counts"]["would_update"] == dry["counts"]["total"]
    assert dry["counts"]["total"] >= 10000


async def test_verify_cie10_passes_on_migrated_schema(cie10_catalog) -> None:
    result = await verify_cie10()

    failed = [c for c in result["checks"] if not c["ok"]]
    assert result["ok"] is True, f"failing checks: {failed}"
    assert result["action"] == "cie10"
    assert result["warnings"] == [], result["warnings"]

    names = {c["name"]: c["ok"] for c in result["checks"]}
    assert names["GIN trigram index ix_cie10_norm_desc_trgm present (§3)"] is True
    assert names["CIE-10 catalog imported (≥ 10000 rows)"] is True
    assert names["nota_diagnosticos: app role cannot DELETE (retention/integrity)"] is True
    assert names["partial unique index uq_nota_diagnostico_principal present (§5.3)"] is True


# ── Trigram / code search ────────────────────────────────────────────────────────────


async def test_search_by_code_prefix_and_dotless(cie10_catalog) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        # E11 → the diabetes family; dotless "E119" resolves to E11.9.
        by_prefix = await _search_by_code(session, "E11", 20, 0)
        assert any(r["code"].startswith("E11") for r in by_prefix), by_prefix
        by_dotless = await _search_by_code(session, "E119", 5, 0)
        assert any(r["code"] == "E11.9" for r in by_dotless), by_dotless


async def test_search_by_description_is_accent_insensitive(cie10_catalog) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        # "colera" (no accent) must match the catalog's "CÓLERA".
        rows = await _search_by_description(session, "colera", 20, 0)
        assert any("A00" in r["code"] for r in rows), rows
        # Common disease name resolves too.
        diab = await _search_by_description(session, "diabetes", 20, 0)
        assert diab, "expected diabetes matches"
        assert all("code" in r and "description" in r for r in diab)


# ── RLS / delete-protection on nota_diagnosticos ────────────────────────────────────


async def test_rls_isolates_nota_diagnosticos(cie10_catalog) -> None:
    _, _, nota_id = await _seed_paciente_expediente_nota(TENANT_A_ID)
    engine = _get_test_engine()
    async with engine.begin() as conn:
        await _insert_diagnostico(
            conn, tenant_id=TENANT_A_ID, nota_id=nota_id, code="E11.9", es_principal=True
        )

    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_B_ID)
            rows = (
                await session.execute(text("SELECT tenant_id FROM nota_diagnosticos"))
            ).scalars().all()
            assert all(str(t) == TENANT_B_ID for t in rows)
        await session.rollback()


async def test_cross_tenant_insert_rejected_by_rls(cie10_catalog) -> None:
    _, _, nota_id = await _seed_paciente_expediente_nota(TENANT_A_ID)
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_B_ID)
            with pytest.raises(DBAPIError) as exc:
                await _insert_diagnostico(
                    session,
                    tenant_id=TENANT_A_ID,
                    nota_id=nota_id,
                    code="E11.9",
                    es_principal=True,
                )
                await session.flush()
            assert "row-level security" in str(exc.value).lower()
        await session.rollback()


async def test_app_role_cannot_delete_diagnostico(cie10_catalog) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            with pytest.raises(DBAPIError) as exc:
                await session.execute(text("DELETE FROM nota_diagnosticos"))
                await session.flush()
            assert "permission denied" in str(exc.value).lower()
        await session.rollback()


async def test_one_principal_per_note_enforced(cie10_catalog) -> None:
    """The partial unique index allows exactly one principal diagnosis per note."""
    _, _, nota_id = await _seed_paciente_expediente_nota(TENANT_A_ID)
    engine = _get_test_engine()
    async with engine.begin() as conn:
        await _insert_diagnostico(
            conn, tenant_id=TENANT_A_ID, nota_id=nota_id, code="E11.9", es_principal=True
        )
    # A second principal for the same note trips uq_nota_diagnostico_principal.
    with pytest.raises(IntegrityError) as exc:
        async with engine.begin() as conn:
            await _insert_diagnostico(
                conn, tenant_id=TENANT_A_ID, nota_id=nota_id, code="I10", es_principal=True
            )
    assert "uq_nota_diagnostico_principal" in str(exc.value)

    # But a non-principal second diagnosis for the same note is fine.
    async with engine.begin() as conn:
        await _insert_diagnostico(
            conn, tenant_id=TENANT_A_ID, nota_id=nota_id, code="I10", es_principal=False
        )


# ── create_nota writes diagnoses create-only (§1.1) ─────────────────────────────────


async def test_create_nota_writes_structured_diagnosticos(
    client: AsyncClient, cie10_catalog
) -> None:
    """End-to-end over HTTP: creating a note with diagnosticos_cie10 writes
    nota_diagnosticos rows with a catalog snapshot, without touching the note afterwards."""
    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}

    _h = uuid.uuid4().hex
    curp = f"DIAA{int(_h[:8], 16) % 1000000:06d}MXYZAB{_h[8].upper()}{int(_h[9], 16) % 10}"
    res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Diagnostico HTTP",
            "sexo": "F",
            "fecha_nacimiento": "1985-05-05",
            "curp": curp,
            "telefono": "555-111-2222",
            "domicilio": "Calle Dx 2",
            "ocupacion": "Ingeniera",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    paciente_id = res.json()["id"]

    res = await client.post(
        "/api/v1/expedientes/", json={"paciente_id": paciente_id}, headers=headers
    )
    assert res.status_code == 201, res.text
    expediente_id = res.json()["id"]

    res = await client.post(
        "/api/v1/notas/",
        json={
            "expediente_id": expediente_id,
            "tipo_nota": "interconsulta",
            "contenido": {"nota": "Paciente con diabetes e hipertensión"},
            "diagnostico_cie10": "E11.9",  # legacy free text still accepted
            "diagnosticos_cie10": [
                {"code": "E11.9", "es_principal": True, "certeza": "confirmado"},
                {"code": "I10", "es_principal": False, "certeza": "presuntivo"},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    nota_id = res.json()["id"]

    engine = _get_test_engine()
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT cie10_code, es_principal, certeza, descripcion_snapshot, "
                    "version_snapshot FROM nota_diagnosticos WHERE nota_id = :n ORDER BY orden"
                ),
                {"n": nota_id},
            )
        ).all()
    assert len(rows) == 2, rows
    principal = [r for r in rows if r.es_principal]
    assert len(principal) == 1 and principal[0].cie10_code == "E11.9"
    # Snapshot was copied from the catalog at creation time.
    assert principal[0].descripcion_snapshot
    assert principal[0].version_snapshot == "CIE-10-MX"

    # The clinical read path returns every structured diagnosis and the canonical
    # note JSON contains the same snapshots so signing covers them.
    res = await client.get(
        f"/api/v1/notas/expediente/{expediente_id}", headers=headers
    )
    assert res.status_code == 200, res.text
    saved = next(item for item in res.json() if item["id"] == nota_id)
    assert [d["code"] for d in saved["diagnosticos_cie10"]] == ["E11.9", "I10"]
    assert saved["diagnosticos_cie10"][0]["es_principal"] is True
    assert saved["contenido"]["diagnosticos_cie10"] == saved["diagnosticos_cie10"]


async def test_create_nota_rejects_two_principal_diagnosticos(
    client: AsyncClient, cie10_catalog
) -> None:
    """Two principal diagnoses in one payload is a readable 422, not a raw 500."""
    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
    _h = uuid.uuid4().hex
    curp = f"DIAB{int(_h[:8], 16) % 1000000:06d}HXYZAB{_h[8].upper()}{int(_h[9], 16) % 10}"
    res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Dos Principales",
            "sexo": "M",
            "fecha_nacimiento": "1970-01-01",
            "curp": curp,
            "telefono": "555-333-4444",
            "domicilio": "Calle Dx 3",
            "ocupacion": "Chofer",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    paciente_id = res.json()["id"]
    res = await client.post(
        "/api/v1/expedientes/", json={"paciente_id": paciente_id}, headers=headers
    )
    expediente_id = res.json()["id"]

    res = await client.post(
        "/api/v1/notas/",
        json={
            "expediente_id": expediente_id,
            "tipo_nota": "interconsulta",
            "contenido": {"nota": "x"},
            "diagnosticos_cie10": [
                {"code": "E11.9", "es_principal": True},
                {"code": "I10", "es_principal": True},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 422, res.text
    assert "principal" in res.text.lower()


# ── Legacy extraction (§1.1: never touches the note) ────────────────────────────────


async def test_extract_legacy_diagnosticos_create_only(cie10_catalog) -> None:
    """Legacy free-text extraction writes a nota_diagnosticos row pointing at the note and
    never UPDATEs the note; re-running is idempotent."""
    _, _, nota_id = await _seed_paciente_expediente_nota(TENANT_A_ID)
    engine = _get_test_engine()
    # Set legacy free text on the freshly-created (unsigned) note via the bypass connection.
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE notas SET diagnostico_cie10 = 'E11.9 - Diabetes' WHERE id = :n"),
            {"n": nota_id},
        )
        before = (
            await conn.execute(
                text("SELECT diagnostico_cie10, es_editable FROM notas WHERE id = :n"),
                {"n": nota_id},
            )
        ).first()

    result = await run_extraction("apply")
    assert result["ok"], result
    assert result["counts"]["inserted"] >= 1

    async with engine.begin() as conn:
        diag = (
            await conn.execute(
                text(
                    "SELECT cie10_code, es_principal FROM nota_diagnosticos WHERE nota_id = :n"
                ),
                {"n": nota_id},
            )
        ).first()
        after = (
            await conn.execute(
                text("SELECT diagnostico_cie10, es_editable FROM notas WHERE id = :n"),
                {"n": nota_id},
            )
        ).first()
    assert diag is not None and diag.cie10_code == "E11.9" and diag.es_principal
    # §1.1: the note's own columns are untouched by extraction.
    assert after.diagnostico_cie10 == before.diagnostico_cie10
    assert after.es_editable == before.es_editable

    # Idempotent: the note already has a diagnosis, so a re-run inserts nothing for it.
    rerun = await run_extraction("apply")
    async with engine.begin() as conn:
        count = (
            await conn.execute(
                text("SELECT count(*) FROM nota_diagnosticos WHERE nota_id = :n"),
                {"n": nota_id},
            )
        ).scalar_one()
    assert count == 1, f"re-run duplicated diagnoses: {count}; rerun={rerun}"
