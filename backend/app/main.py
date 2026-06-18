
"""
CloudMedRecord SaaS — FastAPI Application Entry Point

NOM-004-SSA3-2012 + NOM-024-SSA3-2012 compliant
Electronic Health Record for independent Mexican doctors.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import audit, auth, citas, expedientes, notas, pacientes
from app.core.config import settings
from app.middleware.audit import AuditMiddleware
from app.middleware.tenant import TenantMiddleware

# ── Structured JSON Logging ──
# IMP-09: All logs emitted as JSON for CloudWatch parsing and alerting.

def _configure_logging() -> None:
    """Configure structured JSON logging for CloudWatch compatibility."""
    from pythonjsonlogger.json import JsonFormatter

    formatter = JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Replace handlers with JSON formatter
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)


# ── Security Headers Middleware ──
# IMP-02: Defense-in-depth headers on every API response.

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to every response.

    These headers provide defense-in-depth against:
    - XSS (X-Content-Type-Options, X-Frame-Options)
    - Clickjacking (X-Frame-Options)
    - Information leakage (Referrer-Policy)
    - Downgrade attacks (Strict-Transport-Security)
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"

        # HSTS — only in production (behind TLS)
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application startup and shutdown events."""
    # Startup: configure logging, warm up connections
    _configure_logging()
    logger = logging.getLogger("medrecord.startup")
    logger.info(
        "CloudMedRecord API starting",
        extra={"environment": settings.environment},
    )
    yield
    # Shutdown: clean up


app = FastAPI(
    title="CloudMedRecord API",
    description="Expediente Clínico Electrónico — NOM-004 + NOM-024",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# ── Rate Limit Error Handler ──
# Rate limits for authentication are now handled by Clerk.
# We keep the handler available in case other endpoints are rate limited in the future.

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# ── Middleware (order matters: last added = first executed) ──

# Security headers — runs on every response
app.add_middleware(SecurityHeadersMiddleware)

# CORS — CRIT-04: explicit header whitelist (was allow_headers=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Audit log — logs every request (NOM-004 + NOM-024)
app.add_middleware(AuditMiddleware)

# Tenant isolation — extracts tenant_id from JWT, sets RLS context
app.add_middleware(TenantMiddleware)

# ── Routes ──
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])
app.include_router(pacientes.router, prefix="/api/v1/pacientes", tags=["Pacientes"])
app.include_router(expedientes.router, prefix="/api/v1/expedientes", tags=["Expedientes"])
app.include_router(notas.router, prefix="/api/v1/notas", tags=["Notas Médicas"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Auditoría"])
app.include_router(citas.router, prefix="/api/v1/citas", tags=["Agenda Médica"])


@app.get("/health")
async def health_check() -> Any:
    """Health check endpoint for Route53 and monitoring."""
    return {"status": "ok", "version": "0.1.0"}


# Lambda handler (Mangum adapter)
handler = Mangum(app, lifespan="auto")
