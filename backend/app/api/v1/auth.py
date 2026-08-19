"""
API v1 — Authentication & Registration

Delegates authentication entirely to Clerk.
This router provides the `/me` endpoint to fetch local user context linked to the Clerk JWT.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_reauthentication
from app.core.themes import DEFAULT_THEME, is_valid_theme
from app.db.session import get_db
from app.models.preferencia_interfaz import PreferenciaInterfazUsuario

logger = logging.getLogger("medrecord.auth")

router = APIRouter()


async def _fetch_clerk_primary_email(user_id: str) -> str | None:
    """Return the user's primary verified email from the Clerk API, or None.

    Clerk session tokens frequently omit the email claim, so onboarding cannot
    rely on the JWT alone to dedup tenants. This fetches the authoritative
    address server-side (using the Clerk secret key) as a fallback.
    """
    import httpx

    from app.core.config import get_clerk_secret_key

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.clerk.com/v1/users/{user_id}",
                headers={"Authorization": f"Bearer {get_clerk_secret_key()}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "Could not resolve verified Clerk email",
            extra={"error_code": type(exc).__name__},
        )
        return None

    primary_id = data.get("primary_email_address_id")
    addresses = data.get("email_addresses", [])
    for addr in addresses:
        if addr.get("id") == primary_id:
            return addr.get("email_address")  # type: ignore[no-any-return]
    # Fall back to any verified address if the primary id didn't match.
    for addr in addresses:
        if (addr.get("verification") or {}).get("status") == "verified":
            return addr.get("email_address")  # type: ignore[no-any-return]
    return None


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

    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="User profile not found")

    identity_id = getattr(request.state, "user_id", None)
    tema = DEFAULT_THEME
    if identity_id:
        pref = (
            await db.execute(
                select(PreferenciaInterfazUsuario).where(
                    PreferenciaInterfazUsuario.identity_provider_id == str(identity_id)
                )
            )
        ).scalar_one_or_none()
        if pref is not None and is_valid_theme(pref.tema):
            tema = pref.tema

    return {
        "tenant_id": str(tenant.id),
        "nombre_medico": tenant.nombre_medico,
        "email": tenant.email,
        "notification_email": tenant.notification_email,
        "cedula": tenant.cedula,
        "especialidad": tenant.especialidad,
        "plan": tenant.plan,
        "tema": tema,
    }


class ThemePreferenceUpdate(BaseModel):
    tema: str = Field(..., max_length=50)

    @field_validator("tema")
    @classmethod
    def _validate_tema(cls, v: str) -> str:
        if not is_valid_theme(v):
            raise ValueError("Tema no permitido")
        return v


@router.put("/preferences/theme")
async def update_theme_preference(
    payload: ThemePreferenceUpdate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    """Upsert the current identity's UI theme (Fase 13A).

    Derives tenant + identity from the JWT, validates against the allowlist, and
    writes a single row keyed by (tenant_id, identity_provider_id). It never
    touches professional data or Clerk (that is ``PUT /profile``).
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    identity_id = getattr(request.state, "user_id", None)
    if not tenant_id or not identity_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    pref = (
        await db.execute(
            select(PreferenciaInterfazUsuario).where(
                PreferenciaInterfazUsuario.identity_provider_id == str(identity_id)
            )
        )
    ).scalar_one_or_none()

    if pref is None:
        pref = PreferenciaInterfazUsuario(
            tenant_id=tenant_id,
            identity_provider_id=str(identity_id),
            tema=payload.tema,
        )
        db.add(pref)
    else:
        pref.tema = payload.tema
        pref.modificado_en = datetime.now(timezone.utc)

    await db.flush()
    return {"tema": payload.tema}


class ProfileUpdate(BaseModel):
    cedula: str | None = Field(None, min_length=5, max_length=20)
    especialidad: str | None = None
    # Where cita notifications go. "" clears the override (falls back to email).
    notification_email: str | None = Field(None, max_length=200)

    @field_validator("notification_email")
    @classmethod
    def _validate_notification_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return ""  # explicit clear
        from app.services.email import is_deliverable

        if not is_deliverable(v):
            raise ValueError("Correo de notificaciones inválido o no entregable.")
        return v.lower()


@router.put("/profile")
async def update_profile(
    data: ProfileUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _reauthenticated: None = Depends(require_reauthentication),
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
    if data.notification_email is not None:
        # "" clears the override; a validated address sets it.
        tenant.notification_email = data.notification_email or None

    await db.flush()

    if data.cedula or data.especialidad is not None:
        # §1.3: keep the default credential in lockstep with tenants.cedula.
        from app.services.credenciales import sync_credencial_predeterminada

        await sync_credencial_predeterminada(
            db,
            tenant_id=tenant.id,
            cedula=tenant.cedula,
            especialidad=tenant.especialidad,
        )

    if user_id:
        try:
            import httpx

            from app.core.config import get_clerk_secret_key

            async with httpx.AsyncClient() as client:
                # Update Clerk publicMetadata
                resp = await client.patch(
                    f"https://api.clerk.com/v1/users/{user_id}/metadata",
                    headers={
                        "Authorization": f"Bearer {get_clerk_secret_key()}",
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


class AcceptTermsRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=20)


@router.post("/accept-terms")
async def accept_terms(
    data: AcceptTermsRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    """Record Terms of Service acceptance for the current tenant.

    Idempotent — calling it again simply refreshes the timestamp/version.
    """
    from datetime import datetime, timezone

    from app.models.tenant import Tenant

    tenant_id = request.state.tenant_id
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt)).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    tenant.terms_accepted_at = datetime.now(timezone.utc)
    tenant.terms_version = data.version
    await db.flush()

    return {
        "accepted": True,
        "accepted_at": tenant.terms_accepted_at.isoformat(),
    }


@router.get("/terms-status")
async def terms_status(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    """Return whether the current tenant has accepted the Terms of Service."""
    from app.models.tenant import Tenant

    tenant_id = request.state.tenant_id
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt)).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    return {
        "accepted": tenant.terms_accepted_at is not None,
        "accepted_at": tenant.terms_accepted_at.isoformat() if tenant.terms_accepted_at else None,
        "version": tenant.terms_version,
    }


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

    user_email = getattr(request.state, "user_email", f"doctor_{user_id}@medrecord.local")

    import uuid

    import httpx
    from sqlalchemy import select

    from app.core.config import get_clerk_secret_key
    from app.models.tenant import Tenant

    # The Clerk session token often omits the email claim, so the middleware may
    # have fallen back to a synthetic "*.local" address. Resolve the real verified
    # email from the Clerk API so the self-heal below can re-link this login to an
    # existing (e.g. dev→prod migrated) tenant instead of creating a duplicate.
    if user_email.endswith(".local"):
        resolved_email = await _fetch_clerk_primary_email(user_id)
        if resolved_email:
            logger.info("Resolved verified Clerk email absent from JWT")
            user_email = resolved_email

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

    # Self-heal for the dev→prod migration: Clerk user ids are NOT portable between
    # Clerk instances, so a tenant migrated from dev keeps a stale dev clerk_id and
    # never matches by clerk_id above. Fall back to the verified email and re-link the
    # existing tenant to the current (prod) Clerk user instead of creating a duplicate
    # (which would collide on the unique cédula). Only trust real emails from the JWT,
    # never the synthetic *.local fallbacks set by the middleware.
    if not tenant_row and user_email and not user_email.endswith(".local"):
        stmt = select(Tenant).where(Tenant.email == user_email)
        tenant_row = (await db.execute(stmt)).scalar_one_or_none()
        if tenant_row and tenant_row.clerk_id != user_id:
            logger.info("Re-linking stale Clerk identity during environment migration")
            tenant_row.clerk_id = user_id
            await db.commit()

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
        # Never persist a synthetic/undeliverable address as the tenant identity.
        # If Clerk's token carried no email and the API lookup failed, fail loudly
        # so the user retries — instead of silently creating a tenant whose
        # `email` is `{clerk_id}@test.local` and can never receive notifications.
        from app.services.email import is_deliverable

        if not is_deliverable(user_email):
            logger.error("Onboarding aborted because verified email was unavailable")
            raise HTTPException(
                status_code=422,
                detail=(
                    "No pudimos verificar tu correo electrónico. Cierra sesión, "
                    "vuelve a iniciar sesión e inténtalo de nuevo."
                ),
            )

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

        from sqlalchemy.exc import IntegrityError

        from app.services.credenciales import provision_medico_para_tenant

        try:
            # §1.3 dual-write: a new tenant gets its médico + default credential in the
            # same transaction, so tenants.cedula and the credential are born in sync.
            await provision_medico_para_tenant(
                db,
                tenant_id=new_tenant_id,
                nombre_completo=data.nombre_medico,
                cedula=data.cedula,
                especialidad=data.especialidad or None,
            )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=400,
                detail="La cédula o el correo proporcionado ya se encuentra registrado.",
            ) from None

    # Update Clerk Metadata so future tokens contain the tenant_id
    try:
        clerk_secret_key = get_clerk_secret_key()
    except RuntimeError:
        clerk_secret_key = ""
    if clerk_secret_key:
        try:
            nombre_parts = data.nombre_medico.split()
            first_name = nombre_parts[0] if nombre_parts else ""
            last_name = " ".join(nombre_parts[1:]) if len(nombre_parts) > 1 else ""

            async with httpx.AsyncClient() as client:
                # 1. Update public_metadata using the specific /metadata endpoint
                resp_meta = await client.patch(
                    f"https://api.clerk.com/v1/users/{user_id}/metadata",
                    headers={
                        "Authorization": f"Bearer {clerk_secret_key}",
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
                        "Authorization": f"Bearer {clerk_secret_key}",
                        "Content-Type": "application/json",
                    },
                    json={"first_name": first_name, "last_name": last_name},
                )
                resp_profile.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Clerk metadata update rejected",
                extra={
                    "error_code": "clerk_metadata_update_failed",
                    "upstream_status": exc.response.status_code,
                },
            )
            raise HTTPException(
                status_code=502, detail="No pudimos actualizar la identidad de acceso"
            ) from exc
        except Exception as exc:
            logger.error(
                "Clerk metadata update failed",
                extra={"error_code": type(exc).__name__},
            )
            raise HTTPException(
                status_code=502, detail="No pudimos actualizar la identidad de acceso"
            ) from exc

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
