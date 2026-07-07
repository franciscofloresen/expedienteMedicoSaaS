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
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import (
    audit,
    auth,
    cie10,
    citas,
    expedientes,
    notas,
    pacientes,
    recetas,
    reminders,
)
from app.core.config import settings
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
        if settings.environment == "prod":
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
    docs_url="/docs" if settings.environment != "prod" else None,
    redoc_url=None,
)


# ── Middleware (order matters: last added = first executed) ──

# 4. Tenant isolation — runs closest to the app (extracts tenant_id, auth)
app.add_middleware(TenantMiddleware)

# 2. Security headers — runs early
app.add_middleware(SecurityHeadersMiddleware)

# 1. CORS — CRIT-04: MUST be added LAST so it executes FIRST and catches 401s from TenantMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ── Routes ──
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])
app.include_router(pacientes.router, prefix="/api/v1/pacientes", tags=["Pacientes"])
app.include_router(
    expedientes.router, prefix="/api/v1/expedientes", tags=["Expedientes"]
)
app.include_router(notas.router, prefix="/api/v1/notas", tags=["Notas Médicas"])
app.include_router(citas.router, prefix="/api/v1/citas", tags=["Agenda Médica"])
app.include_router(cie10.router, prefix="/api/v1/cie10", tags=["CIE-10"])
app.include_router(recetas.router, prefix="/api/v1/recetas", tags=["Recetas"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Auditoría"])
app.include_router(
    reminders.router, prefix="/api/v1/reminders", tags=["Recordatorios"]
)


@app.get("/health")
async def health_check() -> Any:
    """Health check endpoint for Route53 and monitoring."""
    return {"status": "ok", "version": "0.1.0"}


# Lambda handler (Mangum adapter)
_asgi_handler = Mangum(app, lifespan="auto")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Custom handler to allow running Alembic migrations securely inside the VPC
    before routing normal HTTP traffic to FastAPI.
    """
    logger = logging.getLogger("medrecord.handler")

    if isinstance(event, dict) and event.get("run_migrations"):
        from alembic.config import Config

        from alembic import command

        logger.info("Running Alembic migrations programmatically...")
        try:
            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")

            logger.info("Migrations applied successfully!")
            return {"statusCode": 200, "body": "Migrations successful!"}
        except Exception as e:
            logger.error("Migrations failed", exc_info=True)
            return {"statusCode": 500, "body": f"Migrations failed: {e}"}

    if isinstance(event, dict) and event.get("upgrade_tenant"):
        import asyncio

        from scripts.upgrade_tenant import upgrade_tenant

        email = event["upgrade_tenant"]
        plan = event.get("plan", "pro")
        logger.info(f"Upgrading tenant {email} to {plan} in production...")
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(upgrade_tenant(email, plan))
            return {"statusCode": 200, "body": f"Successfully upgraded {email} to {plan}"}
        except Exception as e:
            logger.error(f"Failed to upgrade tenant {email}", exc_info=True)
            return {"statusCode": 500, "body": f"Failed to upgrade tenant: {e}"}

    if isinstance(event, dict) and event.get("inspect_cedula"):
        import asyncio

        from scripts.release_cedula import inspect_cedula

        cedula = str(event["inspect_cedula"])
        logger.info(f"Inspecting cédula {cedula} (read-only)...")
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            inspect_result = loop.run_until_complete(inspect_cedula(cedula))
            return {"statusCode": 200, "body": inspect_result}
        except Exception as e:
            logger.error(f"Failed to inspect cédula {cedula}", exc_info=True)
            return {"statusCode": 500, "body": f"Failed to inspect cédula: {e}"}

    if isinstance(event, dict) and event.get("release_cedula"):
        import asyncio

        from scripts.release_cedula import TenantHasDataError, release_cedula

        cedula = str(event["release_cedula"])
        logger.info(f"Releasing cédula {cedula} in production...")
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(release_cedula(cedula))
            return {"statusCode": 200, "body": result}
        except TenantHasDataError as e:
            # Safety guard: tenant has clinical data — nothing was deleted.
            logger.error(f"Release aborted for cédula {cedula}: {e}")
            return {"statusCode": 409, "body": str(e)}
        except Exception as e:
            logger.error(f"Failed to release cédula {cedula}", exc_info=True)
            return {"statusCode": 500, "body": f"Failed to release cédula: {e}"}

    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    return _asgi_handler(event, context)
