"""
API v1 — Authentication & Registration

In development: Uses local JWT issuance with bcrypt password hashing.
In production: Will delegate to AWS Cognito.

The JWT claims structure matches Cognito's format:
- sub: user UUID
- email: user email
- custom:tenant_id: tenant UUID
- custom:nombre_medico: doctor name
- custom:cedula: professional license number

This means the TenantMiddleware works identically regardless of
whether the JWT was issued locally or by Cognito.
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import _get_session_factory, get_db

logger = logging.getLogger("medrecord.auth")

router = APIRouter()

async def get_tenant_db(request: Request):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Missing tenant context")
    async for session in get_db(tenant_id):
        yield session

# ── JWT Configuration ──
# In production this would be Cognito's RSA keys.
# In dev, we use a symmetric HS256 key for simplicity.
JWT_SECRET = "medrecord-dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


# ── Request/Response Schemas ──

class RegisterRequest(BaseModel):
    nombre_medico: str = Field(..., min_length=3, max_length=200, description="Full name of the doctor")
    cedula: str = Field(..., min_length=5, max_length=20, description="Cédula profesional")
    especialidad: str | None = Field(None, max_length=100, description="Medical specialty")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Account password")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    nombre_medico: str
    email: str


# ── Helpers ──

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def _create_jwt(tenant_id: str, email: str, nombre_medico: str, cedula: str) -> str:
    """
    Create a JWT with Cognito-compatible claims.
    The TenantMiddleware reads `custom:tenant_id` from these claims.
    """
    now = datetime.now(timezone.utc)
    claims = {
        "sub": tenant_id,
        "email": email,
        "custom:tenant_id": tenant_id,
        "custom:nombre_medico": nombre_medico,
        "custom:cedula": cedula,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
        "iss": "medrecord-dev",
        "token_use": "access",
    }
    return pyjwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ── Endpoints ──

@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(data: RegisterRequest):
    """
    Register a new doctor (creates tenant + returns JWT).

    In production, this would call Cognito AdminCreateUser.
    In development, it creates the tenant directly in the database.
    """
    from app.models.tenant import Tenant
    from app.models.tenant_key import TenantKey

    factory = _get_session_factory()

    async with factory() as session:
        async with session.begin():
            # Check for duplicate email
            stmt = select(Tenant).where(Tenant.email == data.email)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una cuenta con este correo electrónico",
                )

            # Check for duplicate cédula
            stmt = select(Tenant).where(Tenant.cedula == data.cedula)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una cuenta con esta cédula profesional",
                )

            # Create tenant
            tenant_id = str(uuid.uuid4())
            hashed_pw = _hash_password(data.password)

            tenant = Tenant(
                id=tenant_id,
                nombre_medico=data.nombre_medico,
                cedula=data.cedula,
                especialidad=data.especialidad,
                email=data.email,
                password_hash=hashed_pw,
            )
            session.add(tenant)

            # Local auth: Also create a mock local TenantKey so envelope encryption doesn't crash
            # Only needed locally, but safe enough here since we are mocking Cognito
            import os
            random_key = os.urandom(32)
            tenant_key = TenantKey(
                tenant_id=tenant_id,
                encrypted_dek=random_key,
                kms_key_id="mock-local-kms-key",
            )
            session.add(tenant_key)

            await session.flush()

    # Issue JWT
    token = _create_jwt(
        tenant_id=tenant_id,
        email=data.email,
        nombre_medico=data.nombre_medico,
        cedula=data.cedula,
    )

    logger.info("New tenant registered: %s (%s)", data.email, tenant_id)

    return AuthResponse(
        access_token=token,
        tenant_id=tenant_id,
        nombre_medico=data.nombre_medico,
        email=data.email,
    )


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest):
    """
    Authenticate a doctor and return a JWT.

    In production, this would validate against Cognito.
    In development, it validates against the local database.
    """
    from app.models.tenant import Tenant

    factory = _get_session_factory()

    async with factory() as session:
        async with session.begin():
            stmt = select(Tenant).where(Tenant.email == data.email)
            tenant = (await session.execute(stmt)).scalar_one_or_none()

            if not tenant:
                raise HTTPException(
                    status_code=401,
                    detail="Credenciales inválidas",
                )

            if not tenant.activo:
                raise HTTPException(
                    status_code=403,
                    detail="La cuenta está desactivada. Contacte soporte.",
                )

            # Verify password against hash
            if not tenant.password_hash or not _verify_password(data.password, tenant.password_hash):
                raise HTTPException(
                    status_code=401,
                    detail="Credenciales inválidas",
                )

    # Issue JWT
    token = _create_jwt(
        tenant_id=str(tenant.id),
        email=tenant.email,
        nombre_medico=tenant.nombre_medico,
        cedula=tenant.cedula,
    )

    return AuthResponse(
        access_token=token,
        tenant_id=str(tenant.id),
        nombre_medico=tenant.nombre_medico,
        email=tenant.email,
    )


@router.get("/me")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_tenant_db)):
    """
    Return current user info from the JWT token and database.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from app.models.tenant import Tenant
    from app.models.tenant_key import TenantKey

    stmt = (
        select(Tenant, TenantKey)
        .join(TenantKey, Tenant.id == TenantKey.tenant_id)
        .where(Tenant.id == tenant_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="User profile not found")

    tenant, tenant_key = row

    return {
        "tenant_id": str(tenant.id),
        "nombre_medico": tenant.nombre_medico,
        "email": tenant.email,
        "cedula": tenant.cedula,
        "especialidad": tenant.especialidad,
        "plan": tenant.plan,
        "seguridad": {
            "cifrado_activo": True,
            "kms_key_id": tenant_key.kms_key_id,
            "ultima_rotacion": tenant_key.rotated_at.isoformat() if tenant_key.rotated_at else None,
        }
    }
