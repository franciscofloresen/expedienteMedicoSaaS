"""
Integration test fixtures for MedRecord.

Creates a separate test database and provides test client, database sessions,
and sample data fixtures.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Override environment before importing app
os.environ["ENVIRONMENT"] = "testing"

# Schema-build strategy for the test database.
#   "create_all"  (default) — fast: Base.metadata.create_all + hand-rolled RLS.
#   "migrations"            — runs `alembic upgrade head`, so the tests exercise
#                             the REAL production schema: RLS policies, grants and
#                             immutability triggers created by the migration SQL,
#                             which create_all never emits (§1.4 of the roadmap).
# The migration mode is the only safety net for triggers/RLS/backfills, so the CI
# migration job runs the trigger/RLS-sensitive tests with TEST_SCHEMA_MODE=migrations.
_BACKEND_DIR = Path(__file__).resolve().parents[1]


def use_migrations() -> bool:
    return os.environ.get("TEST_SCHEMA_MODE", "create_all") == "migrations"
# Priority: DATABASE_URL (set by CI) > TEST_DATABASE_URL > local default
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/medrecord_test",
    )

from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402


# Use a separate event loop for the entire test session
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test database engine — points to medrecord_test database
_test_engine = None


def _get_test_engine():
    global _test_engine
    if _test_engine is None:
        db_url = os.environ["DATABASE_URL"]
        _test_engine = create_async_engine(db_url, echo=False)
    return _test_engine


# Test tenant IDs
TENANT_A_ID = "11111111-1111-1111-1111-111111111111"
TENANT_B_ID = "22222222-2222-2222-2222-222222222222"


def _run_migrations() -> None:
    """Build the schema with `alembic upgrade head` in a subprocess.

    A subprocess (not Alembic's Python API) because env.py drives migrations via
    asyncio.run(), which cannot be nested inside this fixture's running event loop.
    Idempotent: a second call against an already-migrated DB is a no-op, so this is
    safe whether or not the CI job also ran `alembic upgrade head` beforehand.
    """
    env = {**os.environ, "DATABASE_URL": os.environ["DATABASE_URL"]}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        env=env,
        check=True,
    )


async def _seed_tenants(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO tenants (id, nombre_medico, cedula, especialidad, email)
                VALUES (:id_a, 'Dr. Tenant A', 'CED-A-001', 'General', 'a@test.com'),
                       (:id_b, 'Dr. Tenant B', 'CED-B-001', 'Cardiología', 'b@test.com')
                ON CONFLICT (id) DO NOTHING
            """
            ),
            {"id_a": TENANT_A_ID, "id_b": TENANT_B_ID},
        )


async def _backfill_medicos(engine) -> None:
    """Give every seeded tenant a médico + default credential (Fase 1).

    Migration mode only: the Fase 1 migration backfill ran against an empty tenants
    table (tenants are seeded afterwards), so we replay the same idempotent INSERTs
    here to reproduce the real post-migration prod state — every tenant has a médico
    and a synced default credential. Runs on the bypass-RLS seed connection and mirrors
    the SQL in migration efb69dbb7dfb exactly.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO medicos (id, tenant_id, nombre_completo, activo)
                SELECT gen_random_uuid(), t.id, t.nombre_medico, true
                FROM tenants t
                WHERE NOT EXISTS (SELECT 1 FROM medicos m WHERE m.tenant_id = t.id)
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO medico_credenciales
                    (id, tenant_id, medico_id, numero, numero_normalizado,
                     tipo, especialidad, es_predeterminada, activa)
                SELECT gen_random_uuid(), t.id, m.id, t.cedula,
                       upper(regexp_replace(coalesce(t.cedula, ''), '\\s+', '', 'g')),
                       'general', t.especialidad, true, true
                FROM tenants t
                JOIN medicos m ON m.tenant_id = t.id
                WHERE coalesce(t.cedula, '') <> ''
                  AND NOT EXISTS (
                      SELECT 1 FROM medico_credenciales c WHERE c.medico_id = m.id
                  )
                """
            )
        )


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Create the schema in the test database once per session.

    Two modes (see TEST_SCHEMA_MODE): ``migrations`` runs the real Alembic chain so
    RLS/grants/triggers match production; ``create_all`` (default) is the fast path
    that hand-rolls a simplified RLS policy for the everyday suite.
    """
    engine = _get_test_engine()

    if use_migrations():
        # The migration chain owns grants, RLS policies (FORCE, no role clause) and
        # the immutability triggers — do NOT hand-roll any of them here.
        _run_migrations()
        await _seed_tenants(engine)
        await _backfill_medicos(engine)
        yield
        # No drop_all: the CI migration DB is throwaway and local re-runs are
        # idempotent. Dropping would also trip the clinical-records immutability
        # trigger on DELETE-bearing teardown paths.
        await engine.dispose()
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Grant permissions to medrecord_app role in the test database
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO medrecord_app"))
        await conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO medrecord_app"
            )
        )
        await conn.execute(
            text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medrecord_app")
        )

        # Enable RLS on core tables
        for table in [
            "pacientes",
            "expedientes",
            "notas",
            "citas",
            "clinical_files",
            "tenant_storage_usage",
        ]:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            # The policy: tenant_id must match the app.current_tenant setting
            await conn.execute(
                text(
                    f"""
                CREATE POLICY tenant_isolation_policy ON {table}
                FOR ALL
                TO medrecord_app
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
                )
            )

    await _seed_tenants(engine)

    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session that rolls back after each test."""
    engine = _get_test_engine()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
        # Rollback after each test to keep tests isolated
        await session.rollback()


@pytest_asyncio.fixture
async def client(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
        # Wait a tick for FastAPI BackgroundTasks (like Audit log) to complete before loop closes
        await asyncio.sleep(0.1)


@pytest_asyncio.fixture
async def client_tenant_a(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Client with Tenant A headers."""
    transport = ASGITransport(app=app)
    hdrs = {"X-Tenant-ID": TENANT_A_ID}
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers=hdrs,
    ) as ac:
        yield ac
        await asyncio.sleep(0.1)


@pytest_asyncio.fixture
async def client_tenant_b(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Client with Tenant B headers."""
    transport = ASGITransport(app=app)
    hdrs = {"X-Tenant-ID": TENANT_B_ID}
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers=hdrs,
    ) as ac:
        yield ac
        await asyncio.sleep(0.1)


@pytest_asyncio.fixture
async def seed_tenant_a(setup_database):
    """Tenant A is seeded in setup_database; this fixture ensures dependency."""
    pass


@pytest_asyncio.fixture
async def seed_tenant_b(setup_database):
    """Tenant B is seeded in setup_database; this fixture ensures dependency."""
    pass
