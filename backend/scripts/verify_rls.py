"""Verify tenant RLS isolation on the clinical file storage tables.

Runs against a migration-built database (NOT create_all): the RLS policies,
grants and FORCE ROW LEVEL SECURITY only exist after `alembic upgrade head`,
so this exercises exactly what production runs.

It mirrors the app's runtime session pattern (app/db/session.py): connect as
the admin user, then `SET LOCAL ROLE medrecord_app` plus
`set_config('app.current_tenant', ...)` per transaction.

Usage:
    ENVIRONMENT=development DATABASE_URL=postgresql+asyncpg://... \
        python scripts/verify_rls.py

Requires the `medrecord_app` role to exist (same as the app runtime) and an
admin DATABASE_URL user that can create seed rows (superuser in CI/local).
Refuses to run against production: it creates and deletes seed data.
"""

import asyncio
import os
import sys
import uuid
from datetime import date
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_database_url
from app.models.clinical_file import ClinicalFile, TenantStorageUsage
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.models.tenant import Tenant

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


async def as_app_role(session: AsyncSession, tenant_id: uuid.UUID | None) -> None:
    """Demote the transaction to the app role, matching app/db/session.py."""
    await session.execute(text("SET LOCAL ROLE medrecord_app"))
    if tenant_id is not None:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(tenant_id)},
        )


def make_seed(tag: str) -> tuple[Tenant, Paciente, Expediente]:
    suffix = uuid.uuid4().hex[:10]
    tenant = Tenant(
        id=uuid.uuid4(),
        nombre_medico=f"RLS Verify {tag}",
        cedula=f"rls{suffix}"[:20],
        email=f"rls-verify-{suffix}@example.invalid",
    )
    paciente = Paciente(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        nombre_completo=f"Paciente RLS {tag}",
        fecha_nacimiento=date(1990, 1, 1),
        sexo="X",
    )
    expediente = Expediente(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        paciente_id=paciente.id,
        folio=f"RLS-{suffix}"[:20],
        creado_por=tenant.id,
    )
    return tenant, paciente, expediente


def make_file(tenant: Tenant, expediente: Expediente) -> ClinicalFile:
    file_id = uuid.uuid4()
    return ClinicalFile(
        id=file_id,
        tenant_id=tenant.id,
        paciente_id=expediente.paciente_id,
        expediente_id=expediente.id,
        s3_key=f"tenants/{tenant.id}/expedientes/{expediente.id}/files/{file_id}/original",
        original_filename="verify.pdf",
        content_type="application/pdf",
        size_bytes=1234,
        uploaded_by="rls-verify",
    )


async def main() -> int:
    if os.environ.get("ENVIRONMENT", "development") == "production":
        print("Refusing to run against production: this script creates seed data.")
        return 2

    # NullPool: each check gets a fresh connection. On a reused pooled
    # connection a previous transaction-local set_config leaves
    # current_setting('app.current_tenant', true) as '' instead of NULL,
    # which makes the policy's ::uuid cast error out (fail-closed) rather
    # than return zero rows. The app never queries without tenant context
    # (get_db raises 403 first), so fresh-connection semantics are the
    # meaningful ones to verify here.
    engine = create_async_engine(get_database_url(), echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tenant_a, paciente_a, expediente_a = make_seed("A")
    tenant_b, paciente_b, expediente_b = make_seed("B")
    all_tenant_ids = [tenant_a.id, tenant_b.id]

    try:
        # Seed as admin (bypasses RLS) — one file per tenant.
        async with factory() as session, session.begin():
            session.add_all([tenant_a, paciente_a, expediente_a])
            session.add_all([tenant_b, paciente_b, expediente_b])
            await session.flush()
            session.add(make_file(tenant_a, expediente_a))
            session.add(make_file(tenant_b, expediente_b))
            session.add(TenantStorageUsage(tenant_id=tenant_a.id, used_bytes=1234))
            session.add(TenantStorageUsage(tenant_id=tenant_b.id, used_bytes=1234))

        print("clinical_files:")
        async with factory() as session, session.begin():
            await as_app_role(session, tenant_a.id)
            rows = (
                (
                    await session.execute(
                        select(ClinicalFile).where(ClinicalFile.tenant_id.in_(all_tenant_ids))
                    )
                )
                .scalars()
                .all()
            )
            check(
                "tenant A sees only its own rows",
                len(rows) == 1 and rows[0].tenant_id == tenant_a.id,
                f"saw {[(str(r.tenant_id)) for r in rows]}",
            )

            result: Any = await session.execute(
                update(ClinicalFile)
                .where(ClinicalFile.tenant_id == tenant_b.id)
                .values(original_filename="hacked.pdf")
            )
            check("cross-tenant UPDATE affects 0 rows", result.rowcount == 0)

        insert_error = ""
        try:
            async with factory() as session, session.begin():
                await as_app_role(session, tenant_a.id)
                session.add(make_file(tenant_b, expediente_b))
                await session.flush()
        except DBAPIError as exc:
            insert_error = str(exc.orig)
        check(
            "cross-tenant INSERT is rejected",
            "row-level security" in insert_error.lower(),
            insert_error or "insert succeeded",
        )

        async with factory() as session, session.begin():
            await as_app_role(session, None)
            rows = (
                (
                    await session.execute(
                        select(ClinicalFile).where(ClinicalFile.tenant_id.in_(all_tenant_ids))
                    )
                )
                .scalars()
                .all()
            )
            check("no tenant context sees no rows", len(rows) == 0)

        print("tenant_storage_usage:")
        async with factory() as session, session.begin():
            await as_app_role(session, tenant_b.id)
            usage_rows = (
                (
                    await session.execute(
                        select(TenantStorageUsage).where(
                            TenantStorageUsage.tenant_id.in_(all_tenant_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            check(
                "tenant B sees only its own usage row",
                len(usage_rows) == 1 and usage_rows[0].tenant_id == tenant_b.id,
            )

            result = await session.execute(
                update(TenantStorageUsage)
                .where(TenantStorageUsage.tenant_id == tenant_a.id)
                .values(used_bytes=0)
            )
            check("cross-tenant usage UPDATE affects 0 rows", result.rowcount == 0)

    finally:
        # Best-effort cleanup of the storage rows only. The seed tenants,
        # pacientes and expedientes stay: the NOM-004 immutability trigger
        # (clinical_records_immutability) blocks DELETE on clinical tables
        # even for superusers, and this script only runs on throwaway DBs.
        try:
            async with factory() as session, session.begin():
                await session.execute(
                    delete(ClinicalFile).where(ClinicalFile.tenant_id.in_(all_tenant_ids))
                )
                await session.execute(
                    delete(TenantStorageUsage).where(
                        TenantStorageUsage.tenant_id.in_(all_tenant_ids)
                    )
                )
        except DBAPIError as exc:
            print(f"  [warn] cleanup skipped: {exc.orig}")
        await engine.dispose()

    if FAILURES:
        print(f"\nRLS verification FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("\nRLS verification passed: tenant isolation is enforced by the migrated policies.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
