"""Fase 1: médicos / medico_credenciales against the REAL migrated schema.

These assertions depend on the migration's RLS policies, partial unique indexes,
REVOKE DELETE and delete-protection triggers — none of which create_all emits — so
the module runs only in migration mode (TEST_SCHEMA_MODE=migrations), the same path
CI's migration job and the production ops-verify workflow exercise.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.medico import Medico, MedicoCredencial
from app.models.tenant import Tenant
from app.services.credenciales import (
    get_credencial_para_firma,
    provision_medico_para_tenant,
    sync_credencial_predeterminada,
)
from scripts.verify_registry import verify_medicos
from tests.conftest import TENANT_A_ID, TENANT_B_ID, _get_test_engine, use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(
        not use_migrations(),
        reason="médicos RLS/uniqueness/triggers require the migrated schema",
    ),
]


def _app_session_factory():
    return async_sessionmaker(_get_test_engine(), class_=AsyncSession, expire_on_commit=False)


async def _as_app_role(session: AsyncSession, tenant_id: str) -> None:
    """Demote to the non-superuser app role and pin the tenant, so RLS actually bites
    (the connection role bypasses RLS otherwise). Reverted by the test's rollback."""
    await session.execute(text("SET LOCAL ROLE medrecord_app"))
    await session.execute(
        text("SELECT set_config('app.current_tenant', :t, true)"), {"t": tenant_id}
    )


async def test_verify_medicos_passes_on_migrated_schema(setup_database) -> None:
    result = await verify_medicos()

    failed = [c for c in result["checks"] if not c["ok"]]
    assert result["ok"] is True, f"failing checks: {failed}"
    assert result["action"] == "medicos"
    # Backfill gave both seeded tenants a médico + synced default credential.
    assert result["counts"]["tenants"] >= 2
    assert result["counts"]["medicos"] >= 2
    assert result["counts"]["credenciales_predeterminadas"] >= 2
    assert result["warnings"] == [], result["warnings"]

    names = {c["name"]: c["ok"] for c in result["checks"]}
    assert names["every tenant has a médico (backfill complete)"] is True
    assert names["tenants.cedula in sync with default credential (§1.3)"] is True


async def test_rls_isolates_medicos_across_tenants(setup_database) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            # A sees only its own médico (the backfilled one), never B's.
            rows = (
                await session.execute(select(Medico.tenant_id))
            ).scalars().all()
            assert rows, "tenant A should see its backfilled médico"
            assert all(str(t) == TENANT_A_ID for t in rows)
        await session.rollback()


async def test_cross_tenant_insert_rejected_by_rls(setup_database) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            # Writing a médico for tenant B while pinned to A violates WITH CHECK.
            with pytest.raises(DBAPIError) as exc:
                await session.execute(
                    text(
                        "INSERT INTO medicos (tenant_id, nombre_completo) "
                        "VALUES (:b, 'Intruso')"
                    ),
                    {"b": TENANT_B_ID},
                )
                await session.flush()
            assert "row-level security" in str(exc.value).lower()
        await session.rollback()


async def test_second_default_active_credential_rejected(setup_database) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            medico_id = (
                await session.execute(select(Medico.id).limit(1))
            ).scalar_one()
            # A already has one default-active credential from the backfill; a second
            # trips the partial unique index uq_credencial_predeterminada_por_medico.
            with pytest.raises(IntegrityError) as exc:
                await session.execute(
                    text(
                        """
                        INSERT INTO medico_credenciales
                            (tenant_id, medico_id, numero, numero_normalizado,
                             es_predeterminada, activa)
                        VALUES (:t, :m, 'OTRA-999', 'OTRA-999', true, true)
                        """
                    ),
                    {"t": TENANT_A_ID, "m": medico_id},
                )
                await session.flush()
            assert "uq_credencial_predeterminada_por_medico" in str(exc.value)
        await session.rollback()


async def test_duplicate_normalized_number_rejected(setup_database) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            medico_id = (
                await session.execute(select(Medico.id).limit(1))
            ).scalar_one()
            existing = (
                await session.execute(
                    select(MedicoCredencial.numero_normalizado)
                    .where(MedicoCredencial.medico_id == medico_id)
                    .limit(1)
                )
            ).scalar_one()
            # A non-default credential (so the default-index doesn't fire first) that
            # reuses the médico's normalized number trips uq_credencial_numero_por_medico.
            with pytest.raises(IntegrityError) as exc:
                await session.execute(
                    text(
                        """
                        INSERT INTO medico_credenciales
                            (tenant_id, medico_id, numero, numero_normalizado,
                             es_predeterminada, activa)
                        VALUES (:t, :m, :num, :norm, false, true)
                        """
                    ),
                    {"t": TENANT_A_ID, "m": medico_id, "num": existing, "norm": existing},
                )
                await session.flush()
            assert "uq_credencial_numero_por_medico" in str(exc.value)
        await session.rollback()


async def test_app_role_cannot_delete_medico_or_credencial(setup_database) -> None:
    factory = _app_session_factory()
    for table in ("medico_credenciales", "medicos"):
        async with factory() as session:
            async with session.begin():
                await _as_app_role(session, TENANT_A_ID)
                with pytest.raises(DBAPIError) as exc:
                    # table is from a hardcoded tuple, not user input.
                    await session.execute(text(f"DELETE FROM {table}"))  # noqa: S608
                    await session.flush()
                # Role-level REVOKE DELETE → permission denied (the trigger is the
                # second line of defense, for the owner/superuser path).
                assert "permission denied" in str(exc.value).lower()
            await session.rollback()


async def test_adapter_reads_default_credential(setup_database) -> None:
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            tenant = (
                await session.execute(select(Tenant).where(Tenant.id == TENANT_A_ID))
            ).scalar_one()
            cred = await get_credencial_para_firma(session, tenant)
            # Comes from the backfilled default credential and stays in sync with the
            # tenant columns (§1.3), so signed-document output is unchanged.
            assert cred.nombre == "Dr. Tenant A"
            assert cred.cedula == "CED-A-001"
            assert cred.especialidad == "General"
        await session.rollback()


async def test_provision_creates_medico_and_default_credential(setup_database) -> None:
    """Onboarding dual-write: a brand-new tenant gets a médico + default credential
    even though onboarding runs under a placeholder RLS context."""
    tenant_c = uuid.UUID("33333333-3333-3333-3333-333333333333")
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL ROLE medrecord_app"))
            # tenants has no RLS policy → insert needs no tenant context.
            await session.execute(
                text(
                    "INSERT INTO tenants (id, nombre_medico, cedula, especialidad, email) "
                    "VALUES (:id, 'Dr. C', 'CED-C-777', 'Pediatría', 'c@test.com') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": str(tenant_c)},
            )
            await provision_medico_para_tenant(
                session,
                tenant_id=tenant_c,
                nombre_completo="Dr. C",
                cedula="CED-C-777",
                especialidad="Pediatría",
            )
            row = (
                await session.execute(
                    select(
                        MedicoCredencial.numero_normalizado,
                        MedicoCredencial.es_predeterminada,
                        MedicoCredencial.activa,
                    )
                    .join(Medico, Medico.id == MedicoCredencial.medico_id)
                    .where(Medico.tenant_id == tenant_c)
                )
            ).first()
            assert row is not None, "provision should create a default credential"
            assert row[0] == "CED-C-777"
            assert row[1] is True and row[2] is True
        await session.rollback()


async def test_sync_updates_default_credential(setup_database) -> None:
    """update_profile keeps the default credential in lockstep with tenants.cedula."""
    tenant_a = uuid.UUID(TENANT_A_ID)
    factory = _app_session_factory()
    async with factory() as session:
        async with session.begin():
            await _as_app_role(session, TENANT_A_ID)
            await sync_credencial_predeterminada(
                session,
                tenant_id=tenant_a,
                cedula="CED-A-XYZ",
                especialidad="Dermatología",
            )
            row = (
                await session.execute(
                    select(
                        MedicoCredencial.numero,
                        MedicoCredencial.numero_normalizado,
                        MedicoCredencial.especialidad,
                    )
                    .join(Medico, Medico.id == MedicoCredencial.medico_id)
                    .where(
                        Medico.tenant_id == tenant_a,
                        MedicoCredencial.es_predeterminada.is_(True),
                        MedicoCredencial.activa.is_(True),
                    )
                )
            ).first()
            assert row[0] == "CED-A-XYZ"
            assert row[1] == "CED-A-XYZ"
            assert row[2] == "Dermatología"
        await session.rollback()
