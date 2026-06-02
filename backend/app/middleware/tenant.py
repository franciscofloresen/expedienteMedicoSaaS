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

from app.core.security import decode_jwt

# Paths that don't require tenant context
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/register"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip public paths
        if request.url.path in PUBLIC_PATHS:
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

        return await call_next(request)
