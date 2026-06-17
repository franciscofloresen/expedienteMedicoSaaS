from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.audit import AuditLog

router = APIRouter()

@router.get("/recent")
async def get_recent_audit_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    limit: int = 20
) -> Any:
    """Obtiene los logs de auditoría más recientes para el tenant actual."""
    tenant_id = getattr(request.state, "tenant_id", None)

    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "metodo": log.method,
            "ruta": log.path,
            "status": log.status_code,
            "tabla": log.tabla,
            "accion": log.accion,
            "timestamp": log.timestamp.isoformat(),
            "exito": log.exito,
            "ip_origen": str(log.ip_origen) if log.ip_origen else "Desconocida",
        }
        for log in logs
    ]

class ConsentimientoRequest(BaseModel):
    paciente_id: UUID

@router.post("/consentimiento")
async def registrar_consentimiento(
    request: Request,
    data: ConsentimientoRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Endpoint para registrar el consentimiento informado explícito.
    No requiere lógica en DB porque el AuditMiddleware captura y
    almacena la petición automáticamente como prueba de auditoría inmutable.
    """
    return {"status": "ok", "evento": "CONSENTIMIENTO_ACEPTADO", "paciente_id": data.paciente_id}
