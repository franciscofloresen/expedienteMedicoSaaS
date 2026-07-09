import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.message_log import MessageLog
from app.models.paciente import Paciente

router = APIRouter()


class WhatsAppManualLogCreate(BaseModel):
    paciente_id: str
    cita_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    template_key: str
    message_preview: str


def _serialize(row: MessageLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "paciente_id": str(row.paciente_id),
        "cita_id": str(row.cita_id) if row.cita_id else None,
        "resource_type": row.resource_type,
        "resource_id": str(row.resource_id) if row.resource_id else None,
        "canal": row.canal,
        "template_key": row.template_key,
        "message_preview": row.message_preview,
        "sent_at": row.sent_at.isoformat(),
    }


@router.post("/log-whatsapp-manual", status_code=201)
async def log_whatsapp_manual(
    data: WhatsAppManualLogCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = uuid.UUID(str(request.state.tenant_id))
    paciente_id = uuid.UUID(data.paciente_id)
    paciente = (
        await db.execute(select(Paciente).where(Paciente.id == paciente_id, Paciente.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    row = MessageLog(
        tenant_id=tenant_id,
        paciente_id=paciente_id,
        cita_id=uuid.UUID(data.cita_id) if data.cita_id else None,
        resource_type=data.resource_type,
        resource_id=uuid.UUID(data.resource_id) if data.resource_id else None,
        canal="whatsapp_manual",
        template_key=data.template_key,
        message_preview=data.message_preview,
        sent_by=tenant_id,
    )
    db.add(row)
    await db.flush()
    return _serialize(row)


@router.get("/paciente/{paciente_id}")
async def list_patient_messages(
    paciente_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = uuid.UUID(str(request.state.tenant_id))
    rows = (
        await db.execute(
            select(MessageLog)
            .where(
                MessageLog.paciente_id == uuid.UUID(paciente_id),
                MessageLog.tenant_id == tenant_id,
            )
            .order_by(MessageLog.sent_at.desc())
        )
    ).scalars().all()
    return [_serialize(row) for row in rows]
