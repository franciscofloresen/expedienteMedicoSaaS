"""
CloudMedRecord SaaS — FastAPI Application Entry Point

NOM-004-SSA3-2012 + NOM-024-SSA3-2012 compliant
Electronic Health Record for independent Mexican doctors.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import (
    audit,
    auth,
    cie10,
    citas,
    consentimientos,
    encuentros,
    expedientes,
    exportacion,
    favoritos,
    files,
    fotografias,
    messages,
    notas,
    pacientes,
    plantillas_nota,
    procedimientos,
    recetas,
    reminders,
    verify,
)
from app.core.config import settings
from app.core.security import ReauthenticationRequiredError
from app.middleware.audit import AuditMiddleware
from app.middleware.request_context import RequestContextFilter, RequestContextMiddleware
from app.middleware.tenant import TenantMiddleware

# ── Structured JSON Logging ──
# IMP-09: All logs emitted as JSON for CloudWatch parsing and alerting.


def _configure_logging() -> None:
    """Configure structured JSON logging for CloudWatch compatibility."""
    from pythonjsonlogger.json import JsonFormatter

    formatter = JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Replace handlers with JSON formatter
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(RequestContextFilter())
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


class ClinicalRolloutMiddleware(BaseHTTPMiddleware):
    """Fail closed for independently routable clinical phases during rollout."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        from app.core.clinical_rollout import feature_enabled

        path = request.url.path
        feature = None
        if path.startswith("/api/v1/encuentros"):
            if not feature_enabled("clinical_encounters"):
                feature = "clinical_encounters"
            elif request.method != "GET" or path.rstrip("/").endswith("/sugerencia"):
                # Stage 3 exposes the deployed encounter read model; classification
                # and all state transitions activate together at stage 4.
                feature = "first_visit_evolution"
        elif path.startswith("/api/v1/cie10"):
            feature = "cie10_catalog"
        if feature and not feature_enabled(feature):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": {
                        "code": "clinical_feature_not_active",
                        "feature": feature,
                    }
                },
            )
        return await call_next(request)


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


@app.exception_handler(ReauthenticationRequiredError)
async def reauthentication_required_handler(
    _request: Request, _exc: ReauthenticationRequiredError
) -> JSONResponse:
    """Return Clerk's standard hint so useReverification can open its MFA modal."""
    return JSONResponse(
        status_code=403,
        content={
            "clerk_error": {
                "type": "forbidden",
                "reason": "reverification-error",
                "metadata": {"reverification": "strict_mfa"},
            }
        },
    )


# ── Middleware (order matters: last added = first executed) ──

# 5. Audit — innermost, so it runs after TenantMiddleware has set tenant_id and
#     can see the final response status. Appends to the immutable bitácora.
app.add_middleware(AuditMiddleware)

# 4. Tenant isolation — runs closest to the app (extracts tenant_id, auth)
app.add_middleware(TenantMiddleware)

# 3. Fase 8 rollout — blocks independently routable features before handlers.
app.add_middleware(ClinicalRolloutMiddleware)

# 2. Security headers — runs early
app.add_middleware(SecurityHeadersMiddleware)

# Correlation ID — generated when absent/invalid and propagated to logs + audit.
app.add_middleware(RequestContextMiddleware)

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
app.include_router(expedientes.router, prefix="/api/v1/expedientes", tags=["Expedientes"])
app.include_router(files.router, prefix="/api/v1/files", tags=["Archivos clínicos"])
app.include_router(notas.router, prefix="/api/v1/notas", tags=["Notas Médicas"])
app.include_router(citas.router, prefix="/api/v1/citas", tags=["Agenda Médica"])
app.include_router(encuentros.router, prefix="/api/v1/encuentros", tags=["Encuentros Clínicos"])
app.include_router(cie10.router, prefix="/api/v1/cie10", tags=["CIE-10"])
app.include_router(recetas.router, prefix="/api/v1/recetas", tags=["Recetas"])
app.include_router(
    consentimientos.router, prefix="/api/v1/consentimientos", tags=["Consentimientos"]
)
app.include_router(messages.router, prefix="/api/v1/messages", tags=["Mensajes"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Auditoría"])
app.include_router(reminders.router, prefix="/api/v1/reminders", tags=["Recordatorios"])
app.include_router(favoritos.router, prefix="/api/v1/favoritos", tags=["Favoritos"])
app.include_router(fotografias.router, prefix="/api/v1/fotografias", tags=["Fotografías clínicas"])
app.include_router(
    plantillas_nota.router, prefix="/api/v1/plantillas-nota", tags=["Plantillas de nota"]
)
app.include_router(
    procedimientos.router, prefix="/api/v1/procedimientos", tags=["Procedimientos"]
)
# Exportación «Descargar todo»: registered at the API root so its routes live at
# /api/v1/expedientes/{id}/exportacion and /api/v1/exportacion/consultorio.
app.include_router(exportacion.router, prefix="/api/v1", tags=["Exportación"])
app.include_router(verify.router, prefix="/verify", tags=["Verificación pública"])


@app.get("/health/live")
@app.get("/health")
async def health_check() -> Any:
    """Process liveness; deliberately exposes no version or internal detail."""
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness_check() -> Any:
    """Readiness requires a bounded, minimal PostgreSQL round trip."""
    from sqlalchemy import text

    from app.db.session import _get_session_factory

    try:
        async with asyncio.timeout(3):
            factory = _get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:  # noqa: BLE001 - public response must stay intentionally opaque
        logging.getLogger("medrecord.health").error(
            "Readiness database check failed",
            extra={"error_code": "database_unavailable"},
        )
        return JSONResponse(status_code=503, content={"status": "unavailable"})




# ── Lambda entry point ──
#
# The deployed Lambda serves two callers: API Gateway (normal HTTP, adapted by
# Mangum) and the operations workflows, which invoke it directly with an
# administrative payload such as {"run_migrations": true}. RDS lives in private
# subnets with no public route, so a payload handled here is the only legitimate
# way to run a migration, an import or a verifier against production.

_asgi_handler = Mangum(app, lifespan="auto")

logger = logging.getLogger("medrecord.handler")


def _ensure_event_loop() -> "asyncio.AbstractEventLoop":
    """Return this execution environment's event loop, creating it if needed.

    A warm Lambda container reuses its loop; a cold one has none yet.
    """
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _run_sync(coro: Any) -> Any:
    """Run a coroutine to completion from Lambda's synchronous handler."""
    return _ensure_event_loop().run_until_complete(coro)


# ── Administrative payloads ──
#
# One function per payload. Each returns the full response; the dispatcher below
# owns logging and the 500 path, so none of them needs a try/except. Imports stay
# inside the functions on purpose: they keep cold starts off the HTTP path.


def _run_migrations(event: dict[str, Any]) -> dict[str, Any]:
    from alembic.config import Config

    from alembic import command

    command.upgrade(Config("alembic.ini"), "head")
    logger.info("Migrations applied successfully")
    return {"statusCode": 200, "body": "Migrations successful!"}


def _verify(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.verify_registry import run_verify

    result = run_verify(str(event["verify"]))
    return {"statusCode": 200 if result.get("ok") else 500, "body": result}


def _import_cie10(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.import_cie10 import run_import_sync

    result = run_import_sync(str(event["import_cie10"]))
    return {"statusCode": 200 if result.get("ok") else 400, "body": result}


def _import_consent_templates(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.import_consent_templates import run_import_sync

    result = run_import_sync(
        str(event["import_consent_templates"]),
        str(event.get("consent_template_catalog", "baseline")),
    )
    return {"statusCode": 200 if result.get("ok") else 400, "body": result}


def _extract_legacy_diagnosticos(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.extract_legacy_diagnosticos import run_extraction_sync

    result = run_extraction_sync(str(event["extract_legacy_diagnosticos"]))
    return {"statusCode": 200 if result.get("ok") else 400, "body": result}


def _verify_file_storage(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.verify_file_storage import run_phase

    result = run_phase(event["verify_file_storage"], s3_key=event.get("s3_key"))
    return {"statusCode": 200 if result.get("ok") else 500, "body": result}


def _upgrade_tenant(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.upgrade_tenant import upgrade_tenant

    email = str(event["upgrade_tenant"])
    plan = str(event.get("plan", "pro"))
    _run_sync(upgrade_tenant(email, plan))
    return {"statusCode": 200, "body": f"Successfully upgraded {email} to {plan}"}


def _upgrade_tenant_id(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.upgrade_tenant import upgrade_tenant_by_id

    tenant_id = str(event["upgrade_tenant_id"])
    plan = str(event.get("plan", "pro"))
    _run_sync(upgrade_tenant_by_id(tenant_id, plan))
    return {"statusCode": 200, "body": f"Successfully upgraded tenant {tenant_id} to {plan}"}


def _inspect_cedula(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.release_cedula import inspect_cedula

    return {"statusCode": 200, "body": _run_sync(inspect_cedula(str(event["inspect_cedula"])))}


def _inspect_email(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.release_cedula import inspect_email

    return {"statusCode": 200, "body": _run_sync(inspect_email(str(event["inspect_email"])))}


def _release_cedula(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.release_cedula import TenantHasDataError, release_cedula

    cedula = str(event["release_cedula"])
    try:
        return {"statusCode": 200, "body": _run_sync(release_cedula(cedula))}
    except TenantHasDataError as exc:
        # Safety guard: the tenant has clinical data — nothing was deleted.
        logger.error("Release aborted for cédula %s: %s", cedula, exc)
        return {"statusCode": 409, "body": str(exc)}


def _release_email(event: dict[str, Any]) -> dict[str, Any]:
    from scripts.release_cedula import TenantHasDataError, release_email

    email = str(event["release_email"])
    try:
        return {"statusCode": 200, "body": _run_sync(release_email(email))}
    except TenantHasDataError as exc:
        # Safety guard: the tenant has clinical data — nothing was deleted.
        logger.error("Release aborted for email %s: %s", email, exc)
        return {"statusCode": 409, "body": str(exc)}


# Event key → handler. Checked in order; the first key with a truthy value wins.
# Adding a payload is one entry plus one function.
_ADMIN_PAYLOADS: tuple[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]], ...] = (
    ("run_migrations", _run_migrations),
    ("verify", _verify),
    ("import_cie10", _import_cie10),
    ("import_consent_templates", _import_consent_templates),
    ("extract_legacy_diagnosticos", _extract_legacy_diagnosticos),
    ("verify_file_storage", _verify_file_storage),
    ("upgrade_tenant", _upgrade_tenant),
    ("upgrade_tenant_id", _upgrade_tenant_id),
    ("inspect_cedula", _inspect_cedula),
    ("release_cedula", _release_cedula),
    ("inspect_email", _inspect_email),
    ("release_email", _release_email),
)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Route an administrative payload, or hand the event to FastAPI."""
    if isinstance(event, dict):
        for key, run in _ADMIN_PAYLOADS:
            if not event.get(key):
                continue
            logger.info("Running administrative payload %s", key)
            try:
                return run(event)
            except Exception as exc:  # noqa: BLE001 — every payload reports, never crashes
                logger.error("Administrative payload %s failed", key, exc_info=True)
                return {"statusCode": 500, "body": f"{key} failed: {exc}"}

    _ensure_event_loop()
    return _asgi_handler(event, context)
