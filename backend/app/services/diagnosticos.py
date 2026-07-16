"""Structured CIE-10 diagnoses attached to a note (Fase 3).

Create-only by design (§1.1): diagnoses are written when a note is created (or,
best-effort, by the legacy-extraction admin payload) and point **at** the note. A signed
note is immutable, so it is never UPDATEd to carry a diagnosis. The one-principal-per-note
rule is enforced by the partial unique index ``uq_nota_diagnostico_principal``; here we
also raise a readable error before hitting the DB so the API can return a clean 4xx.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cie10 import CIE10
from app.models.nota_diagnostico import NotaDiagnostico

CERTEZAS = ("confirmado", "presuntivo", "descartado")


class DiagnosticoInvalidoError(Exception):
    """A diagnosis payload is invalid (unknown code, bad certeza, or >1 principal)."""


@dataclass
class DiagnosticoInput:
    code: str
    es_principal: bool = False
    certeza: str = "presuntivo"
    orden: int | None = None


async def crear_diagnosticos_para_nota(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    nota_id: uuid.UUID,
    diagnosticos: list[DiagnosticoInput],
    creado_por: uuid.UUID | None = None,
) -> list[NotaDiagnostico]:
    """Insert the note's diagnoses, snapshotting the catalog text/version at write time.

    Validates up front (readable :class:`DiagnosticoInvalidoError`, mapped to 4xx by the
    caller): every code must exist in ``cie10``, every ``certeza`` must be valid, and at
    most one diagnosis may be ``es_principal``. The DB partial unique index is the
    race-proof backstop for the principal rule.
    """
    if not diagnosticos:
        return []

    if sum(1 for d in diagnosticos if d.es_principal) > 1:
        raise DiagnosticoInvalidoError(
            "Sólo un diagnóstico puede marcarse como principal por nota."
        )
    for d in diagnosticos:
        if d.certeza not in CERTEZAS:
            raise DiagnosticoInvalidoError(f"Certeza inválida: {d.certeza!r}")

    # One lookup for all codes; snapshot description + catalog version from the catalog.
    codes = [d.code for d in diagnosticos]
    catalog = {
        c.code: c
        for c in (
            await db.execute(select(CIE10).where(CIE10.code.in_(codes)))
        ).scalars()
    }
    faltantes = [c for c in codes if c not in catalog]
    if faltantes:
        raise DiagnosticoInvalidoError(
            f"Código(s) CIE-10 no encontrado(s): {', '.join(sorted(set(faltantes)))}"
        )

    filas: list[NotaDiagnostico] = []
    for i, d in enumerate(diagnosticos):
        cat = catalog[d.code]
        fila = NotaDiagnostico(
            tenant_id=tenant_id,
            nota_id=nota_id,
            cie10_code=d.code,
            orden=d.orden if d.orden is not None else i,
            es_principal=d.es_principal,
            certeza=d.certeza,
            descripcion_snapshot=cat.description,
            version_snapshot=cat.catalog_version,
            creado_por=creado_por,
        )
        db.add(fila)
        filas.append(fila)
    await db.flush()
    return filas
