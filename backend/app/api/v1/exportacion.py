"""Exportación «Descargar todo» — portabilidad de datos del médico (LFPDPPP).

Deliberately NOT gated by plan: data portability is a right, not a Pro feature.
Both endpoints require step-up reauthentication — this is the most sensitive
bulk read in the system — and both are recorded in the audit bitácora by the
audit middleware (NOM-024).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_reauthentication
from app.db.session import get_db
from app.schemas.exportacion import ExportacionExpediente, IndiceConsultorioExport
from app.services.exportacion import build_consultorio_index, build_expediente_export

router = APIRouter()


def _tenant_uuid(request: Request) -> uuid.UUID:
    try:
        return uuid.UUID(str(request.state.tenant_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=403, detail="Contexto de clínica inválido") from exc


@router.get(
    "/expedientes/{expediente_id}/exportacion",
    response_model=ExportacionExpediente,
    response_model_exclude_none=False,
)
async def exportar_expediente(
    expediente_id: uuid.UUID,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _reauthenticated: None = Depends(require_reauthentication),
) -> ExportacionExpediente:
    """Full export of one patient's expediente: clinical content inline, binaries
    as short-lived presigned URLs (quarantined files are listed, never linked)."""
    tenant_id = _tenant_uuid(request)
    documento = await build_expediente_export(
        db, tenant_id=tenant_id, expediente_id=expediente_id
    )
    if documento is None:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="cloudmedrecord-expediente-{documento.expediente.folio}.json"'
    )
    return documento


@router.get(
    "/exportacion/consultorio",
    response_model=IndiceConsultorioExport,
)
async def exportar_indice_consultorio(
    request: Request,
    response: Response,
    cursor: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _reauthenticated: None = Depends(require_reauthentication),
) -> IndiceConsultorioExport:
    """Tenant-wide index: patients, folios and per-type document counts — no
    binaries and no clinical content. Paginated by ``?cursor=`` past 500 rows."""
    tenant_id = _tenant_uuid(request)
    response.headers["Content-Disposition"] = (
        'attachment; filename="cloudmedrecord-indice-consultorio.json"'
    )
    return await build_consultorio_index(db, tenant_id=tenant_id, cursor=cursor)
