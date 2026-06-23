"""
Integration test fixtures for MedRecord.

Creates a separate test database and provides test client, database sessions,
and sample data fixtures.
"""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Override environment before importing app
os.environ["ENVIRONMENT"] = "testing"
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

@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Create all tables in the test database once per session."""
    engine = _get_test_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Grant permissions to medrecord_app role in the test database
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO medrecord_app"))
        await conn.execute(text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO medrecord_app"
        ))
        await conn.execute(text(
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medrecord_app"
        ))

        # Enable RLS on core tables
        for table in ["pacientes", "expedientes", "notas", "citas", "audit_log", "tenant_keys"]:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            # The policy: tenant_id must match the app.current_tenant setting
            await conn.execute(text(f"""
                CREATE POLICY tenant_isolation_policy ON {table}
                FOR ALL
                TO medrecord_app
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """))

        # Seed Tenants
        await conn.execute(
            text("""
                INSERT INTO tenants (id, nombre_medico, cedula, especialidad, email)
                VALUES (:id_a, 'Dr. Tenant A', 'CED-A-001', 'General', 'a@test.com'),
                       (:id_b, 'Dr. Tenant B', 'CED-B-001', 'Cardiología', 'b@test.com')
                ON CONFLICT (id) DO NOTHING
            """),
            {"id_a": TENANT_A_ID, "id_b": TENANT_B_ID},
        )
        dek = b"\x00" * 32  # 32-byte mock DEK
        await conn.execute(
            text(
                "INSERT INTO tenant_keys"
                " (tenant_id, kms_key_id, encrypted_dek)"
                " VALUES (:id_a, 'mock-kms-a', :dek_a),"
                " (:id_b, 'mock-kms-b', :dek_b)"
                " ON CONFLICT (tenant_id) DO NOTHING"
            ),
            {
                "id_a": TENANT_A_ID,
                "id_b": TENANT_B_ID,
                "dek_a": dek,
                "dek_b": dek,
            },
        )
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
        transport=transport, base_url="http://testserver", headers=hdrs,
    ) as ac:
        yield ac
        await asyncio.sleep(0.1)


@pytest_asyncio.fixture
async def client_tenant_b(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Client with Tenant B headers."""
    transport = ASGITransport(app=app)
    hdrs = {"X-Tenant-ID": TENANT_B_ID}
    async with AsyncClient(
        transport=transport, base_url="http://testserver", headers=hdrs,
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
