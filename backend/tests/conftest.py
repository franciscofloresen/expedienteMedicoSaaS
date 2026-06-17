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
os.environ["ENVIRONMENT"] = "development"
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


# Test tenant IDs
TENANT_A_ID = "11111111-1111-1111-1111-111111111111"
TENANT_B_ID = "22222222-2222-2222-2222-222222222222"


@pytest_asyncio.fixture
async def client(setup_database) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
        # Wait a tick for FastAPI BackgroundTasks (like Audit log) to complete before loop closes
        await asyncio.sleep(0.1)


@pytest_asyncio.fixture
async def client_tenant_a(client: AsyncClient) -> AsyncClient:
    """Client with Tenant A headers."""
    client.headers["X-Tenant-ID"] = TENANT_A_ID
    return client


@pytest_asyncio.fixture
async def client_tenant_b(client: AsyncClient) -> AsyncClient:
    """Client with Tenant B headers."""
    client.headers["X-Tenant-ID"] = TENANT_B_ID
    return client


@pytest_asyncio.fixture
async def seed_tenant_a(db_session: AsyncSession):
    """Seed Tenant A with a tenant, patient, and expediente."""
    await db_session.execute(
        text("""
            INSERT INTO tenants (id, nombre_medico, cedula, especialidad, email)
            VALUES (:id, 'Dr. Tenant A', 'CED-A-001', 'General', 'a@test.com')
            ON CONFLICT (id) DO NOTHING
        """),
        {"id": TENANT_A_ID},
    )
    await db_session.flush()


@pytest_asyncio.fixture
async def seed_tenant_b(db_session: AsyncSession):
    """Seed Tenant B."""
    await db_session.execute(
        text("""
            INSERT INTO tenants (id, nombre_medico, cedula, especialidad, email)
            VALUES (:id, 'Dr. Tenant B', 'CED-B-001', 'Cardiología', 'b@test.com')
            ON CONFLICT (id) DO NOTHING
        """),
        {"id": TENANT_B_ID},
    )
    await db_session.flush()
