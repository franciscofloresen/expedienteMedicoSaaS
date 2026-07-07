"""
Tenant Isolation Middleware

Extracts tenant_id from the Clerk JWT token and sets the PostgreSQL
session variable `app.current_tenant` for Row-Level Security.
"""

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.security import decode_jwt

# Paths that don't require tenant context
PUBLIC_PATHS = {
    "/health",
    "/docs",
}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
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
                import logging
                logging.getLogger("medrecord.security").error(f"JWT Validation Error: {e}")
                return JSONResponse(
                    status_code=401,
                    content={"detail": f"Token inválido o expirado: {e}"},
                )

            # Clerk puts custom claims in publicMetadata or custom JWT template
            metadata = claims.get("metadata", claims.get("public_metadata", {}))
            tenant_id = (
                claims.get("tenant_id")
                or claims.get("custom:tenant_id")
                or metadata.get("tenant_id")
            )

        # Solo permitido en pruebas automatizadas (tests), NUNCA en development o production
        if not tenant_id and settings.environment == "testing":
            tenant_id = request.headers.get("X-Tenant-ID")
            claims = {"sub": "test-user", "email": "test@test.com"}
            # Test-only hook to exercise plan entitlements (mirrors X-Tenant-ID).
            test_plan = request.headers.get("X-Plan")
            if test_plan:
                claims["plan"] = test_plan

        if not tenant_id:
            # Allow onboarding path without tenant_id if they have a valid token
            if request.url.path == "/api/v1/auth/onboarding" and claims:
                pass
            else:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Token de autenticación requerido o tenant_id faltante"
                    },
                )

        request.state.tenant_id = tenant_id

        user_id = claims.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido: falta claim 'sub'")
        request.state.user_id = user_id
        request.state.user_email = claims.get("email") or metadata.get(
            "email", f"{claims.get('sub', 'dev')}@test.local"
        )
        request.state.user_name = claims.get("nombre_medico") or metadata.get(
            "nombre_medico"
        )
        request.state.user_cedula = claims.get("cedula") or metadata.get("cedula")
        request.state.user_especialidad = claims.get("especialidad") or metadata.get(
            "especialidad"
        )
        request.state.plan = claims.get("plan") or metadata.get("plan") or "basico"
        return await call_next(request)
