"""Audit Middleware — NOM-004/NOM-024 bitácora writer.

Appends one immutable row to `audit_log` per auditable request:
  - every write (POST/PUT/PATCH/DELETE) under /api/v1  → modificaciones/eliminaciones
  - reads of an individual clinical record (GET .../{id})  → accesos

Writes are best-effort: an audit failure is logged but never breaks the user's
request. Immutability + tenant-scoped reads are enforced at the DB level.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("medrecord.audit")

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Clinical resources whose individual-record reads count as an "acceso".
_CLINICAL_PREFIXES = (
    "/api/v1/pacientes",
    "/api/v1/expedientes",
    "/api/v1/notas",
    "/api/v1/recetas",
)


def _should_audit(method: str, path: str) -> bool:
    """Audit all writes under the API, plus reads of an individual clinical record."""
    if method in _WRITE_METHODS:
        return path.startswith("/api/v1/")
    if method == "GET":
        for prefix in _CLINICAL_PREFIXES:
            # A sub-segment after the resource means "a specific record",
            # not the list/search root (e.g. /api/v1/pacientes/{id}).
            if path.startswith(prefix + "/") and len(path) > len(prefix) + 1:
                return True
    return False


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)

        try:
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id and _should_audit(request.method, request.url.path):
                await self._record(
                    tenant_id=str(tenant_id),
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    ip=_client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    request_id=request.headers.get("x-request-id"),
                    duration_ms=(time.monotonic() - start) * 1000,
                )
        except Exception as e:  # noqa: BLE001 — audit must never break the request
            logger.warning(f"Audit write failed for {request.url.path}: {e}")

        return response

    async def _record(
        self,
        *,
        tenant_id: str,
        method: str,
        path: str,
        status_code: int,
        ip: str | None,
        user_agent: str | None,
        request_id: str | None,
        duration_ms: float,
    ) -> None:
        from sqlalchemy import text

        from app.db.session import _get_session_factory
        from app.models.audit_log import AuditLog

        factory = _get_session_factory()
        async with factory() as session:
            async with session.begin():
                # Enforce RLS as the least-privilege app role (append-only).
                await session.execute(text("SET LOCAL ROLE medrecord_app"))
                await session.execute(
                    text("SELECT set_config('app.current_tenant', :tid, true)"),
                    {"tid": tenant_id},
                )
                session.add(
                    AuditLog(
                        tenant_id=uuid.UUID(tenant_id),
                        accion=method,
                        method=method,
                        path=path,
                        status_code=status_code,
                        ip_origen=ip,
                        user_agent=user_agent,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )
                )
