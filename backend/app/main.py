"""
MedRecord SaaS — FastAPI Application Entry Point

NOM-004-SSA3-2012 + NOM-024-SSA3-2012 compliant
Electronic Health Record for independent Mexican doctors.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.api.v1 import auth, expedientes, notas, pacientes
from app.core.config import settings
from app.middleware.audit import AuditMiddleware
from app.middleware.tenant import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup: warm up connections, cache secrets
    yield
    # Shutdown: clean up


app = FastAPI(
    title="MedRecord API",
    description="Expediente Clínico Electrónico — NOM-004 + NOM-024",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

# ── Middleware (order matters: last added = first executed) ──

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
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


@app.get("/health")
async def health_check():
    """Health check endpoint for Route53 and monitoring."""
    return {"status": "ok", "version": "0.1.0"}


# Lambda handler (Mangum adapter)
handler = Mangum(app, lifespan="auto")
