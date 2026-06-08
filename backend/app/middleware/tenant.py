"""
Tenant Isolation Middleware

Extracts tenant_id from the JWT token and sets the PostgreSQL
session variable `app.current_tenant` for Row-Level Security.

This middleware works in tandem with RLS policies — even if the
middleware has a bug, RLS prevents cross-tenant data access.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.config import settings
from app.core.security import decode_jwt

# Paths that don't require tenant context
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/register"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip public paths and CORS preflight OPTIONS requests
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Dev bypass: allow X-Tenant-ID header in development ONLY
        if request.headers.get("X-Tenant-ID"):
            if settings.environment != "development":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "X-Tenant-ID header is not allowed in production"},
                )
            import logging
            logging.getLogger("medrecord.security").warning(
                "Dev bypass: using X-Tenant-ID header for tenant %s",
                request.headers.get("X-Tenant-ID"),
            )
            request.state.tenant_id = request.headers.get("X-Tenant-ID")
            request.state.user_id = "00000000-0000-0000-0000-000000000000"  # Must be valid UUID for audit cast
            request.state.user_email = "dev@local.host"
            request.state.user_name = "Dr. Local Dev"
            request.state.user_cedula = "DEV-00000"
            request.state.user_especialidad = "General"
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token de autenticación requerido"},
            )

        token = auth_header.split(" ", 1)[1]

        try:
            claims = decode_jwt(token)
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido o expirado"},
            )

        tenant_id = claims.get("custom:tenant_id")
        if not tenant_id:
            return JSONResponse(
                status_code=403,
                content={"detail": "Token sin tenant_id asociado"},
            )

        # Store tenant_id and user info in request state
        # The DB session will use this to SET LOCAL "app.current_tenant"
        request.state.tenant_id = tenant_id
        request.state.user_id = claims.get("sub")
        request.state.user_email = claims.get("email")
        request.state.user_name = claims.get("custom:nombre_medico", "Médico Titular")
        request.state.user_cedula = claims.get("custom:cedula", "ND")
        request.state.user_especialidad = claims.get("custom:especialidad", "General")

        return await call_next(request)
