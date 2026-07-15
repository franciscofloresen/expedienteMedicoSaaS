"""Encounter lifecycle: type suggestion and state transitions.

Fase 2 (roadmap §5.2/§6.3). The "primera vez / subsecuente" decision is a
**suggestion** computed from the patient's completed-encounter history; the real
enforcement of "only one first consultation" is the partial unique index
``uq_encuentro_primera_vez`` (§3), race-proof where transactional validation is not.

All queries run under the caller's RLS context (encuentros are tenant-scoped), so
they only ever see the current tenant's rows.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encuentro import EncuentroClinico

# Encounter types and states (mirror the DB CHECK constraints).
TIPOS = ("primera_vez", "subsecuente", "procedimiento", "urgencia", "otro")
ESTADOS = ("programado", "iniciado", "completado", "cancelado")


class PrimeraVezDuplicadaError(Exception):
    """Raised when completing a ``primera_vez`` would create a second one for the
    patient — the partial unique index rejected it. Callers map this to HTTP 409."""


async def sugerir_tipo_encuentro(
    db: AsyncSession, paciente_id: uuid.UUID
) -> str:
    """Suggest ``primera_vez`` if the patient has no completed encounter yet, else
    ``subsecuente``. A suggestion only — the definitive decision happens when the
    encounter is completed, and the partial unique index is the real guard (§3).

    A cancelled encounter never counts (only ``estado='completado'`` is inspected),
    so a cancelled first visit does not turn the next one into a subsecuente.
    """
    tiene_completado = (
        await db.execute(
            select(func.count())
            .select_from(EncuentroClinico)
            .where(
                EncuentroClinico.paciente_id == paciente_id,
                EncuentroClinico.estado == "completado",
            )
        )
    ).scalar_one()
    return "subsecuente" if tiene_completado else "primera_vez"


async def completar_encuentro(
    db: AsyncSession, encuentro: EncuentroClinico
) -> EncuentroClinico:
    """Mark an encounter as completed, honoring the one-primera_vez rule.

    Completing a ``primera_vez`` when the patient already has a completed one trips
    ``uq_encuentro_primera_vez``; we translate that IntegrityError into a readable
    :class:`PrimeraVezDuplicadaError` (→ 409) instead of leaking a raw 500. The
    savepoint keeps the outer transaction usable for the error path.
    """
    from datetime import datetime, timezone

    encuentro.estado = "completado"
    if encuentro.fecha_fin is None:
        encuentro.fecha_fin = datetime.now(timezone.utc)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        if "uq_encuentro_primera_vez" in str(exc.orig):
            raise PrimeraVezDuplicadaError(
                "El paciente ya tiene una consulta de primera vez completada."
            ) from exc
        raise
    return encuentro
