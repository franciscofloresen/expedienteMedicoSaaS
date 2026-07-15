"""Fase 2: encuentros_clinicos against the REAL migrated schema.

These assertions depend on the migration's RLS policies, the partial unique index
``uq_encuentro_primera_vez``, REVOKE DELETE and the delete-protection trigger — none
of which create_all emits — so the module runs only in migration mode
(TEST_SCHEMA_MODE=migrations), the same path CI's migration job and the production
ops-verify workflow exercise.

The headline test is the **concurrency** check (§264 acceptance): two overlapping
transactions racing to complete a ``primera_vez`` for the same patient — exactly one
wins, the other trips the partial unique index. That is the guarantee that transactional
validation could not give race-free (§3).
"""

import asyncio
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.encuentro import EncuentroClinico
from app.services.encuentros import sugerir_tipo_encuentro
from scripts.verify_registry import verify_encuentros
from tests.conftest import TENANT_A_ID, TENANT_B_ID, _get_test_engine, use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(
        not use_migrations(),
        reason="encuentros RLS/partial-index/triggers require the migrated schema",
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


async def _seed_paciente_expediente(tenant_id: str) -> tuple[str, str, str]:
    """Create a fresh paciente + expediente for a tenant on the bypass-RLS seed
    connection, plus return the tenant's backfilled médico id. Random ids per call so
    committed (undeletable) rows from one test never collide with another or a re-run.
    """
    engine = _get_test_engine()
    paciente_id = str(uuid.uuid4())
    expediente_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex[:8]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO pacientes (id, tenant_id, nombre_completo, fecha_nacimiento, sexo) "
                "VALUES (:id, :t, 'Paciente Encuentro', '1990-01-01', 'X')"
            ),
            {"id": paciente_id, "t": tenant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO expedientes (id, tenant_id, paciente_id, folio, creado_por) "
                "VALUES (:id, :t, :p, :folio, :t)"
            ),
            {"id": expediente_id, "t": tenant_id, "p": paciente_id, "folio": f"ENC-{suffix}"},
        )
        medico_id = (
            await conn.execute(
                text("SELECT id FROM medicos WHERE tenant_id = :t LIMIT 1"), {"t": tenant_id}
            )
        ).scalar_one()
    return paciente_id, expediente_id, str(medico_id)


async def _insert_encuentro(
    conn,
    *,
    tenant_id: str,
    paciente_id: str,
    expediente_id: str,
    medico_id: str,
    tipo: str,
    estado: str,
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO encuentros_clinicos
                (tenant_id, paciente_id, expediente_id, medico_id, tipo, estado)
            VALUES (:t, :p, :e, :m, :tipo, :estado)
            """
        ),
        {
            "t": tenant_id,
            "p": paciente_id,
            "e": expediente_id,
            "m": medico_id,
            "tipo": tipo,
            "estado": estado,
        },
    )


async def test_verify_encuentros_passes_on_migrated_schema(setup_database) -> None:
    result = await verify_encuentros()

    failed = [c for c in result["checks"] if not c["ok"]]
    assert result["ok"] is True, f"failing checks: {failed}"
    assert result["action"] == "encuentros"
    assert result["warnings"] == [], result["warnings"]

    names = {c["name"]: c["ok"] for c in result["checks"]}
    assert names["partial unique index uq_encuentro_primera_vez present (§3)"] is True
    assert names["at most one completed primera_vez per patient (§3)"] is True
    assert names["encuentros_clinicos: app role cannot DELETE (retention/integrity)"] is True


async def test_rls_isolates_encuentros_across_tenants(setup_database) -> None:
    paciente_id, expediente_id, medico_id = await _seed_paciente_expediente(TENANT_A_ID)
    # Seed one encuentro for A on the bypass connection.
    engine = _get_test_engine()
    async with engine.begin() as conn:
        await _insert_encuentro(
            conn,
            tenant_id=TENANT_A_ID,
            paciente_id=paciente_id,
            expediente_id=expediente_id,
            medico_id=medico_id,
            tipo="subsecuente",
            estado="programado",
        )

    factory = _app_session_factory()
    # Pinned to B, A's encuentro is invisible.
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_B_ID)
            rows = (await session.execute(select(EncuentroClinico.tenant_id))).scalars().all()
            assert all(str(t) == TENANT_B_ID for t in rows)
        await session.rollback()


async def test_cross_tenant_insert_rejected_by_rls(setup_database) -> None:
    paciente_id, expediente_id, medico_id = await _seed_paciente_expediente(TENANT_A_ID)
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            # Pinned to B, writing an encuentro for A's tenant_id violates WITH CHECK.
            await _as_app_role(session, TENANT_B_ID)
            with pytest.raises(DBAPIError) as exc:
                await _insert_encuentro(
                    session,
                    tenant_id=TENANT_A_ID,
                    paciente_id=paciente_id,
                    expediente_id=expediente_id,
                    medico_id=medico_id,
                    tipo="subsecuente",
                    estado="programado",
                )
                await session.flush()
            assert "row-level security" in str(exc.value).lower()
        await session.rollback()


async def test_app_role_cannot_delete_encuentro(setup_database) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            with pytest.raises(DBAPIError) as exc:
                await session.execute(text("DELETE FROM encuentros_clinicos"))
                await session.flush()
            # REVOKE DELETE → permission denied (trigger is the owner-path backstop).
            assert "permission denied" in str(exc.value).lower()
        await session.rollback()


async def test_sugerencia_primera_vez_then_subsecuente(setup_database) -> None:
    paciente_id, expediente_id, medico_id = await _seed_paciente_expediente(TENANT_A_ID)
    factory = _app_session_factory()

    # No completed encounter yet → primera_vez.
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            tipo = await sugerir_tipo_encuentro(session, uuid.UUID(paciente_id))
            assert tipo == "primera_vez"
        await session.rollback()

    # A completed primera_vez exists → next suggestion is subsecuente.
    engine = _get_test_engine()
    async with engine.begin() as conn:
        await _insert_encuentro(
            conn,
            tenant_id=TENANT_A_ID,
            paciente_id=paciente_id,
            expediente_id=expediente_id,
            medico_id=medico_id,
            tipo="primera_vez",
            estado="completado",
        )
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            tipo = await sugerir_tipo_encuentro(session, uuid.UUID(paciente_id))
            assert tipo == "subsecuente"
        await session.rollback()


async def test_cancelled_primera_vez_does_not_count(setup_database) -> None:
    """A cancelled first visit must not turn the next encounter into a subsecuente."""
    paciente_id, expediente_id, medico_id = await _seed_paciente_expediente(TENANT_A_ID)
    engine = _get_test_engine()
    async with engine.begin() as conn:
        await _insert_encuentro(
            conn,
            tenant_id=TENANT_A_ID,
            paciente_id=paciente_id,
            expediente_id=expediente_id,
            medico_id=medico_id,
            tipo="primera_vez",
            estado="cancelado",
        )
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            tipo = await sugerir_tipo_encuentro(session, uuid.UUID(paciente_id))
            assert tipo == "primera_vez"
        await session.rollback()


async def test_concurrent_primera_vez_only_one_wins(setup_database) -> None:
    """Two overlapping transactions race to complete a primera_vez for the same
    patient. The partial unique index lets exactly one commit; the other trips
    ``uq_encuentro_primera_vez``. This is the race-free guarantee of §3 that
    transactional validation could not provide (§264 acceptance)."""
    paciente_id, expediente_id, medico_id = await _seed_paciente_expediente(TENANT_A_ID)
    factory = _app_session_factory()

    async def _complete_primera_vez() -> str:
        """Insert a completed primera_vez in its own transaction. Returns 'ok' or the
        error text. Both start before either commits, so they genuinely overlap."""
        async with factory() as session:
            try:
                async with session.begin():
                    await _as_app_role(session, TENANT_A_ID)
                    await _insert_encuentro(
                        session,
                        tenant_id=TENANT_A_ID,
                        paciente_id=paciente_id,
                        expediente_id=expediente_id,
                        medico_id=medico_id,
                        tipo="primera_vez",
                        estado="completado",
                    )
                    await session.flush()
                return "ok"
            except IntegrityError as exc:
                return str(exc.orig)

    results = await asyncio.gather(
        _complete_primera_vez(), _complete_primera_vez()
    )

    oks = [r for r in results if r == "ok"]
    conflicts = [r for r in results if r != "ok"]
    assert len(oks) == 1, f"expected exactly one winner, got {results}"
    assert len(conflicts) == 1
    assert "uq_encuentro_primera_vez" in conflicts[0], conflicts[0]
