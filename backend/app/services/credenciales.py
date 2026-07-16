"""Single source of the professional identity stamped onto signed documents.

Fase 1 introduces ``medicos`` / ``medico_credenciales`` but the three signing flows
(consentimientos, notas, recetas — ~30 read sites of ``tenant.cedula`` /
``nombre_medico`` / ``especialidad``) must not each reinvent the lookup. They all go
through :func:`get_credencial_para_firma`.

During the transition ``tenants.cedula`` is kept in lockstep with the default
credential (§1.3), so the credential-derived values are byte-for-byte identical to the
old ``tenant.*`` values — consent text and signatures do not change. If a tenant has no
default credential yet (edge case), it falls back to the ``tenants`` columns, so no flow
can break while the new model rolls out.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credenciales import normalize_credential_number
from app.models.medico import Medico, MedicoCredencial
from app.models.tenant import Tenant


@dataclass(frozen=True)
class CredencialFirma:
    """The doctor identity to stamp on a signed document. ``especialidad`` is already
    defaulted to ``"General"`` so callers use it verbatim."""

    nombre: str
    cedula: str
    especialidad: str
    medico_id: uuid.UUID | None = None
    credencial_id: uuid.UUID | None = None


async def get_credencial_para_firma(db: AsyncSession, tenant: Tenant) -> CredencialFirma:
    """Resolve the signing identity for ``tenant`` from its default-active credential.

    Falls back per-field to the ``tenants`` columns, then fully to them if the tenant has
    no default credential. Runs under the caller's RLS context (the credential is
    tenant-scoped), so it only ever sees the current tenant's médico.
    """
    row = (
        await db.execute(
            select(
                Medico.id,
                MedicoCredencial.id,
                Medico.nombre_completo,
                MedicoCredencial.numero,
                MedicoCredencial.especialidad,
            )
            .join(MedicoCredencial, MedicoCredencial.medico_id == Medico.id)
            .where(
                Medico.tenant_id == tenant.id,
                MedicoCredencial.es_predeterminada.is_(True),
                MedicoCredencial.activa.is_(True),
            )
            .limit(1)
        )
    ).first()

    if row is not None:
        medico_id, credencial_id, nombre, numero, especialidad = row
        return CredencialFirma(
            nombre=nombre or tenant.nombre_medico,
            cedula=numero or tenant.cedula,
            especialidad=especialidad or tenant.especialidad or "General",
            medico_id=medico_id,
            credencial_id=credencial_id,
        )

    return CredencialFirma(
        nombre=tenant.nombre_medico,
        cedula=tenant.cedula,
        especialidad=tenant.especialidad or "General",
    )


async def list_credenciales_para_firma(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[dict[str, str | bool]]:
    """List active credentials available for an explicit document signature."""
    rows = (
        await db.execute(
            select(Medico, MedicoCredencial)
            .join(MedicoCredencial, MedicoCredencial.medico_id == Medico.id)
            .where(
                Medico.tenant_id == tenant_id,
                Medico.activo.is_(True),
                MedicoCredencial.activa.is_(True),
            )
            .order_by(
                MedicoCredencial.es_predeterminada.desc(),
                MedicoCredencial.especialidad,
                MedicoCredencial.numero,
            )
        )
    ).all()
    return [
        {
            "medico_id": str(medico.id),
            "credencial_id": str(credencial.id),
            "nombre": medico.nombre_completo,
            "cedula": credencial.numero,
            "especialidad": credencial.especialidad or "General",
            "tipo": credencial.tipo,
            "es_predeterminada": credencial.es_predeterminada,
            "verificada": credencial.verificada,
        }
        for medico, credencial in rows
    ]


async def get_credencial_seleccionada_para_firma(
    db: AsyncSession,
    tenant: Tenant,
    credencial_id: uuid.UUID | None,
) -> CredencialFirma:
    """Resolve an explicitly selected active credential, or the safe default adapter."""
    if credencial_id is None:
        return await get_credencial_para_firma(db, tenant)
    row = (
        await db.execute(
            select(Medico, MedicoCredencial)
            .join(MedicoCredencial, MedicoCredencial.medico_id == Medico.id)
            .where(
                Medico.tenant_id == tenant.id,
                Medico.activo.is_(True),
                MedicoCredencial.id == credencial_id,
                MedicoCredencial.activa.is_(True),
            )
        )
    ).first()
    if row is None:
        raise ValueError("La credencial seleccionada no está activa o no pertenece al tenant")
    medico, credencial = row
    return CredencialFirma(
        nombre=medico.nombre_completo,
        cedula=credencial.numero,
        especialidad=credencial.especialidad or "General",
        medico_id=medico.id,
        credencial_id=credencial.id,
    )


async def provision_medico_para_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    nombre_completo: str,
    cedula: str | None,
    especialidad: str | None,
) -> Medico:
    """Create the médico + default credential for a brand-new tenant (§1.3 dual-write).

    Called from onboarding. Pins the RLS context to ``tenant_id`` first, because
    onboarding runs under a placeholder tenant context and RLS ``WITH CHECK`` would
    otherwise reject the writes. Must run inside the caller's transaction (it flushes
    but does not commit).
    """
    await db.execute(
        text("SELECT set_config('app.current_tenant', :t, true)"),
        {"t": str(tenant_id)},
    )
    medico = Medico(tenant_id=tenant_id, nombre_completo=nombre_completo)
    db.add(medico)
    await db.flush()

    cedula = (cedula or "").strip()
    if cedula:
        db.add(
            MedicoCredencial(
                tenant_id=tenant_id,
                medico_id=medico.id,
                numero=cedula,
                numero_normalizado=normalize_credential_number(cedula),
                tipo="general",
                especialidad=especialidad or None,
                es_predeterminada=True,
                activa=True,
            )
        )
        await db.flush()
    return medico


async def sync_credencial_predeterminada(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    cedula: str | None,
    especialidad: str | None,
) -> None:
    """Keep the default-active credential in lockstep with ``tenants.cedula`` (§1.3).

    Called from ``update_profile`` when the doctor edits their cédula/especialidad, so
    onboarding's uniqueness check and ``release_cedula`` keep matching the credential.
    Runs under the caller's own (correct) tenant context. No-op if there is no cédula.
    Note: ``medico_credenciales`` has no UPDATE-immutability trigger, so editing the
    default credential in place is allowed (unlike signed notas).
    """
    cedula = (cedula or "").strip()
    if not cedula:
        return
    normalized = normalize_credential_number(cedula)

    cred = (
        await db.execute(
            select(MedicoCredencial)
            .join(Medico, Medico.id == MedicoCredencial.medico_id)
            .where(
                Medico.tenant_id == tenant_id,
                MedicoCredencial.es_predeterminada.is_(True),
                MedicoCredencial.activa.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if cred is not None:
        cred.numero = cedula
        cred.numero_normalizado = normalized
        if especialidad is not None:
            cred.especialidad = especialidad or None
        await db.flush()
        return

    # No default credential yet (e.g. a tenant that had an empty cédula at backfill).
    # Attach one to the médico if it exists; otherwise leave it to the adapter fallback.
    medico = (
        await db.execute(select(Medico).where(Medico.tenant_id == tenant_id).limit(1))
    ).scalar_one_or_none()
    if medico is None:
        return
    db.add(
        MedicoCredencial(
            tenant_id=tenant_id,
            medico_id=medico.id,
            numero=cedula,
            numero_normalizado=normalized,
            tipo="general",
            especialidad=especialidad or None,
            es_predeterminada=True,
            activa=True,
        )
    )
    await db.flush()
