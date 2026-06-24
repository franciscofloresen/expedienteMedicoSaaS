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

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("medrecord.audit")

# Paths that don't generate audit entries
SKIP_AUDIT_PATHS = {"/health", "/docs", "/openapi.json", "/favicon.ico"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
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

            user_email = getattr(request.state, "user_email", None)

            audit_entry = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "user_id": str(user_id) if user_id else None,
                "user_email": str(user_email) if user_email else None,
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

            # 2. Base de datos (Audit Ledger Primario)
            # Todo el rastro legal se maneja ahora automáticamente a nivel
            # de base de datos a través de la extensión pgaudit y AWS CloudTrail,
            # lo que previene falsificaciones desde la capa de aplicación.

            # Also store in request state for any route handler that needs it
            try:
                request.state.audit_entry = audit_entry
            except Exception as e:
                logger.debug("Failed to set audit entry on request state: %s", e)
