"""
Database Session Management with RLS Tenant Context

Critical: The application database role (medrecord_app) is NOT a superuser.
Superusers bypass RLS policies. The app MUST connect as a non-superuser role
for Row-Level Security to be enforced.

On every request:
1. Acquire connection from RDS Proxy pool
2. SET LOCAL "app.current_tenant" = tenant_id (scoped to transaction)
3. All queries within the transaction are filtered by RLS
4. Connection returned to pool on commit/rollback
"""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Lazy initialization — engine is created on first request, not at import time.
# This avoids calling get_database_url() (which hits Secrets Manager in prod)
# during module import, which can fail before Lambda env vars are set.
_engine = None
_async_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        from app.core.config import get_database_url
        _engine = create_async_engine(
            get_database_url(),
            echo=False,
            pool_size=5,       # Lambda: keep small (RDS Proxy handles pooling)
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=300,   # 5 min — match RDS Proxy idle timeout
            pool_pre_ping=True, # Verify connection before use
        )
    return _engine


def _get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session with RLS tenant context.

    Usage in route handlers:
        @router.get("/pacientes")
        async def list_pacientes(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Paciente))
            # RLS automatically filters to current tenant's data
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        if request.url.path == "/api/v1/auth/onboarding":
            # For onboarding, we don't have a tenant yet.
            # We use a dummy UUID. The route handler will override this when creating the tenant.
            tenant_id = "00000000-0000-0000-0000-000000000000"
        else:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Missing tenant context")

    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            # Demote connection to application role to enforce RLS (superusers bypass RLS)
            await session.execute(text("SET LOCAL ROLE medrecord_app"))
            # SET LOCAL scopes the variable to the current transaction ONLY
            # When the transaction commits or rolls back, the setting is cleared
            # This prevents tenant context leaking between requests
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                {"tenant_id": tenant_id},
            )
            yield session

            # Transaction auto-commits on successful exit
            # Auto-rolls back on exception
