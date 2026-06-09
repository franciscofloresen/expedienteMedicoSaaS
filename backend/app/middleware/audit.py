"""
Audit Middleware — NOM-004 + NOM-024 Compliance

Logs EVERY request to the audit_log table. This is legally required:
- NOM-004: all access to clinical records must be logged
- NOM-024: audit trail of all system operations

This middleware writes to both:
1. The audit_log database table (primary, legally required)
2. CloudWatch structured logs (secondary, for observability)

Audit records are NEVER updated or deleted — enforced by a DB trigger.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("medrecord.audit")

# Paths that don't generate audit entries
SKIP_AUDIT_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS" or request.url.path in SKIP_AUDIT_PATHS:
            return await call_next(request)

        start_time = time.monotonic()
        request_id = str(uuid.uuid4())

        # Capture request metadata
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")[:500]

        # Store request_id for use in route handlers
        request.state.request_id = request_id

        # Execute request
        status_code = 500
        error_detail: str | None = None
        success = True

        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                success = False
                error_detail = f"HTTP {status_code}"
            return response
        except Exception as exc:
            success = False
            error_detail = str(exc)[:500]  # Truncate to prevent log bloat
            raise
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000

            # Build audit entry
            tenant_id = getattr(request.state, "tenant_id", None)
            user_id = getattr(request.state, "user_id", None)

            audit_entry = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "user_id": str(user_id) if user_id else None,
                "ip_origen": client_ip,
                "user_agent": user_agent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "exito": success,
                "error_detalle": error_detail,
            }

            # 1. Write to CloudWatch logs as structured JSON (secondary channel)
            logger.info(json.dumps(audit_entry, ensure_ascii=False))

            # 2. Write to database (primary audit ledger)
            # Uses a separate session to ensure audit persists even if the
            # request transaction rolled back.
            from app.core.config import settings
            if settings.environment != "testing" or request_id.startswith("test-audit-"):
                await self._persist_audit(audit_entry)

            # Also store in request state for any route handler that needs it
            try:
                request.state.audit_entry = audit_entry
            except Exception:
                pass  # Request state may be unavailable in error scenarios

    async def _persist_audit(self, entry: dict) -> None:
        """
        Write audit entry to the database using a separate, short-lived session.

        This is intentionally isolated from the request's transactional session:
        - If the request fails and rolls back, the audit record still persists.
        - If the audit write fails, it does NOT crash the user's request.
        """
        from app.core.config import settings
        if settings.environment == "testing" and not entry.get("request_id", "").startswith("test-audit-"):
            # Avoid BaseHTTPMiddleware cross-loop asyncio bugs in pytest
            return

        try:
            from app.db.session import _get_session_factory

            factory = _get_session_factory()
            async with factory() as session:
                async with session.begin():
                    # Use raw SQL to avoid importing the model here (circular dep risk)
                    # and to keep this as lightweight as possible.
                    await session.execute(
                        text("""
                            INSERT INTO audit_log (
                                request_id, method, path, tenant_id, usuario_id,
                                ip_origen, user_agent, status_code, duration_ms,
                                exito, error_detalle
                            ) VALUES (
                                :request_id, :method, :path,
                                CAST(:tenant_id AS uuid), CAST(:usuario_id AS uuid),
                                CAST(:ip_origen AS inet), :user_agent,
                                :status_code, :duration_ms,
                                :exito, :error_detalle
                            )
                        """),
                        {
                            "request_id": entry["request_id"],
                            "method": entry["method"],
                            "path": entry["path"],
                            "tenant_id": entry.get("tenant_id"),
                            "usuario_id": entry.get("user_id"),
                            "ip_origen": entry["ip_origen"],
                            "user_agent": entry["user_agent"],
                            "status_code": entry["status_code"],
                            "duration_ms": entry["duration_ms"],
                            "exito": entry["exito"],
                            "error_detalle": entry.get("error_detalle"),
                        },
                    )
        except Exception as exc:
            # Audit persistence failure must NOT crash the request.
            # But it MUST be logged loudly — this is a compliance alarm.
            logger.error(
                "CRITICAL: Failed to persist audit log to database: %s | entry=%s",
                exc,
                json.dumps(entry, ensure_ascii=False),
            )
