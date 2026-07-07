"""API v1 — Audit Log (read-only bitácora view).

Surfaces the immutable, tenant-scoped `audit_log` table to the frontend. Reads
are filtered to the current tenant by RLS (audit_read_own). Pro-only feature.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import entitlement
from app.db.session import get_db
from app.models.audit_log import AuditLog

logger = logging.getLogger("medrecord.audit")

router = APIRouter()


class AuditEntry(BaseModel):
    timestamp: datetime
    action: str  # e.g. "POST /api/v1/pacientes/"
    status_code: int | None
    ip_address: str | None


@router.get("/", response_model=list[AuditEntry])
async def list_audit(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEntry]:
    """Return recent audit activity for the current tenant (read-only, Pro-only).

    Rows are scoped to the tenant by RLS; ordered newest first.
    """
    plan = getattr(request.state, "plan", "basico")
    if not entitlement(plan, "audit_log"):
        raise HTTPException(
            status_code=403,
            detail="El registro de auditoría está disponible sólo en el plan Pro.",
        )

    stmt = (
        select(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return [
        AuditEntry(
            timestamp=r.timestamp,
            action=f"{r.method or r.accion or ''} {r.path or ''}".strip(),
            status_code=r.status_code,
            ip_address=str(r.ip_origen) if r.ip_origen is not None else None,
        )
        for r in rows
    ]
