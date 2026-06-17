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
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip public paths and CORS preflight OPTIONS requests
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
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
            # For this integration, we expect tenant_id to be provided in the token.
            metadata = claims.get("metadata", claims.get("public_metadata", {}))
            tenant_id = (
                claims.get("tenant_id") or
                claims.get("custom:tenant_id") or
                metadata.get("tenant_id")
            )

            if not tenant_id:
                # Allow onboarding path without tenant_id
                if request.url.path == "/api/v1/auth/onboarding":
                    pass
                else:
                    # For dev demo without Clerk metadata configured, fallback to X-Tenant-ID
                    if settings.environment == "development":
                        tenant_id = request.headers.get("X-Tenant-ID")
                    if not tenant_id:
                        return JSONResponse(
                            status_code=403,
                            content={
                                "detail": "Token sin tenant_id asociado "
                                          "(requiere configuración de Clerk JWT)"
                            },
                        )

            request.state.tenant_id = tenant_id
            request.state.user_id = claims.get("sub")
            request.state.user_email = claims.get("email") or metadata.get("email", "")
            request.state.user_name = claims.get("nombre_medico") or metadata.get(
                "nombre_medico", "Médico Titular"
            )
            request.state.user_cedula = claims.get("cedula") or metadata.get("cedula", "ND")
            request.state.user_especialidad = claims.get("especialidad") or metadata.get(
                "especialidad", "General"
            )
            return await call_next(request)


        return JSONResponse(
            status_code=401,
            content={"detail": "Token de autenticación requerido"},
        )


