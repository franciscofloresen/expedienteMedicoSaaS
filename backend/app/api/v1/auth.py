"""
API v1 — Authentication & Registration

Delegates authentication entirely to Clerk.
This router provides the `/me` endpoint to fetch local user context linked to the Clerk JWT.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

logger = logging.getLogger("medrecord.auth")

router = APIRouter()

# ── Endpoints ──


@router.get("/me")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Return current user info from the JWT token and database.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from app.models.tenant import Tenant

    stmt = (
        select(Tenant)
        .where(Tenant.id == tenant_id)
    )
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="User profile not found")

    return {
        "tenant_id": str(tenant.id),
        "nombre_medico": tenant.nombre_medico,
        "email": tenant.email,
        "cedula": tenant.cedula,
        "especialidad": tenant.especialidad,
        "plan": tenant.plan,
    }


class ProfileUpdate(BaseModel):
    cedula: str | None = Field(None, min_length=5, max_length=20)
    especialidad: str | None = None


@router.put("/profile")
async def update_profile(
    data: ProfileUpdate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    from sqlalchemy import select

    from app.models.tenant import Tenant

    tenant_id = request.state.tenant_id
    user_id = getattr(request.state, "user_id", None)

    stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt)).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    if data.cedula:
        tenant.cedula = data.cedula
    if data.especialidad is not None:
        tenant.especialidad = data.especialidad

    await db.flush()

    if user_id:
        try:
            import httpx

            from app.core.config import settings

            async with httpx.AsyncClient() as client:
                # Update Clerk publicMetadata
                resp = await client.patch(
                    f"https://api.clerk.com/v1/users/{user_id}/metadata",
                    headers={
                        "Authorization": f"Bearer {settings.clerk_secret_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "public_metadata": {
                            "tenant_id": str(tenant_id),
                            "nombre_medico": tenant.nombre_medico,
                            "cedula": tenant.cedula,
                            "especialidad": tenant.especialidad,
                        }
                    },
                )
                resp.raise_for_status()
        except Exception as e:
            import logging

            logging.getLogger("medrecord.auth").warning(
                f"Failed to update Clerk metadata for {user_id}: {e}"
            )

    await db.commit()

    return {"status": "success"}


class OnboardingRequest(BaseModel):
    nombre_medico: str = Field(..., min_length=2, max_length=200)
    cedula: str = Field(..., min_length=5, max_length=20)
    especialidad: str | None = None


@router.post("/onboarding")
async def onboarding(
    data: OnboardingRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Onboarding flow: Create a new Tenant and TenantKey for a user who just signed up via Clerk.
    """
    # The user is authenticated via Clerk but doesn't have a tenant yet
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="No authenticated Clerk user found")

    user_email = getattr(
        request.state, "user_email", f"doctor_{user_id}@medrecord.local"
    )

    import uuid

    import httpx
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.tenant import Tenant

    # Check if they already have a tenant
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id:
        # Check if it actually exists in DB
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return {"status": "already_onboarded", "tenant_id": str(tenant_id)}

    # Check if they already have a tenant by clerk_id (Idempotency check)
    stmt = select(Tenant).where(Tenant.clerk_id == user_id)
    existing_tenant = await db.execute(stmt)
    tenant_row = existing_tenant.scalar_one_or_none()

    if tenant_row:
        new_tenant_id = tenant_row.id
        tenant_profile = {
            "id": str(tenant_row.id),
            "clerk_id": tenant_row.clerk_id,
            "nombre_medico": tenant_row.nombre_medico,
            "cedula": tenant_row.cedula,
            "especialidad": tenant_row.especialidad,
            "email": tenant_row.email,
            "plan": tenant_row.plan,
        }
    else:
        new_tenant_id = uuid.uuid4()

        # Create Tenant
        new_tenant = Tenant(
            id=new_tenant_id,
            clerk_id=user_id,
            nombre_medico=data.nombre_medico,
            cedula=data.cedula,
            especialidad=data.especialidad or "General",
            email=user_email,
            plan="basico",
        )
        db.add(new_tenant)

        await db.commit()

    # Update Clerk Metadata so future tokens contain the tenant_id
    if settings.clerk_secret_key:
        try:
            nombre_parts = data.nombre_medico.split()
            first_name = nombre_parts[0] if nombre_parts else ""
            last_name = " ".join(nombre_parts[1:]) if len(nombre_parts) > 1 else ""

            async with httpx.AsyncClient() as client:
                # 1. Update public_metadata using the specific /metadata endpoint
                resp_meta = await client.patch(
                    f"https://api.clerk.com/v1/users/{user_id}/metadata",
                    headers={
                        "Authorization": f"Bearer {settings.clerk_secret_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "public_metadata": {
                            "tenant_id": str(new_tenant_id),
                            "cedula": data.cedula,
                            "nombre_medico": data.nombre_medico,
                            "especialidad": data.especialidad or "General",
                            "plan": "basico",
                        }
                    },
                )
                resp_meta.raise_for_status()

                # 2. Update first_name and last_name using the main user endpoint
                resp_profile = await client.patch(
                    f"https://api.clerk.com/v1/users/{user_id}",
                    headers={
                        "Authorization": f"Bearer {settings.clerk_secret_key}",
                        "Content-Type": "application/json",
                    },
                    json={"first_name": first_name, "last_name": last_name},
                )
                resp_profile.raise_for_status()
        except httpx.HTTPStatusError as e:
            err_text = e.response.text
            logger.error(
                f"Failed to update Clerk metadata for {user_id}: {e} - "
                f"Response: {err_text}"
            )
            # Raise an exception so frontend actually fails and shows the error
            raise HTTPException(
                status_code=500, detail=f"Error actualizando Clerk: {err_text}"
            ) from e
        except Exception as e:
            logger.error(f"Failed to update Clerk metadata for {user_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Error interno: {str(e)}"
            ) from e

    if not tenant_row:
        tenant_profile = {
            "id": str(new_tenant_id),
            "clerk_id": user_id,
            "nombre_medico": data.nombre_medico,
            "cedula": data.cedula,
            "especialidad": data.especialidad or "General",
            "email": user_email,
            "plan": "basico",
        }

    return {
        "status": "success" if not tenant_row else "already_onboarded",
        "tenant_id": str(new_tenant_id),
        "tenant": tenant_profile,
        "message": "Onboarding completado",
    }
