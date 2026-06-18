"""
Tenant Isolation Middleware

Extracts tenant_id from the Clerk JWT token and sets the PostgreSQL
session variable `app.current_tenant` for Row-Level Security.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.security import decode_jwt

# Paths that don't require tenant context
PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/openapi.json",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip public paths and CORS preflight OPTIONS requests
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        tenant_id = None
        claims = {}
        metadata = {}

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                claims = decode_jwt(token)
            except Exception as e:
                return JSONResponse(
                    status_code=401,
                    content={"detail": f"Token inválido o expirado: {e}"},
                )

            # Clerk puts custom claims in publicMetadata or custom JWT template
            metadata = claims.get("metadata", claims.get("public_metadata", {}))
            tenant_id = (
                claims.get("tenant_id") or
                claims.get("custom:tenant_id") or
                metadata.get("tenant_id")
            )

        # Fallback for dev demo without Clerk metadata configured
        if not tenant_id and settings.environment == "development":
            tenant_id = request.headers.get("X-Tenant-ID")

        if not tenant_id:
            # Allow onboarding path without tenant_id if they have a valid token
            if request.url.path == "/api/v1/auth/onboarding" and claims:
                pass
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token de autenticación requerido o tenant_id faltante"},
                )

        request.state.tenant_id = tenant_id
        request.state.user_id = claims.get("sub", "dev-user")
        request.state.user_email = claims.get("email") or metadata.get("email", "dev@test.com")
        request.state.user_name = claims.get("nombre_medico") or metadata.get(
            "nombre_medico", "Médico Titular"
        )
        request.state.user_cedula = claims.get("cedula") or metadata.get("cedula", "ND")
        request.state.user_especialidad = claims.get("especialidad") or metadata.get(
            "especialidad", "General"
        )
        return await call_next(request)


