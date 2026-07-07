"""API v1 — Reminders / Recordatorios.

In-app appointment reminders. Tenant-scoped via RLS (tenant_id from JWT only).
Reminders are NOT clinical records, so hard delete is permitted.
"""

import logging
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.reminder import Reminder
from app.schemas.reminder import ReminderCreate, ReminderResponse, ReminderUpdate

logger = logging.getLogger("medrecord.reminders")
router = APIRouter()


@router.get("/", response_model=List[ReminderResponse])
async def list_reminders(
    request: Request,
    include_dismissed: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List reminders for the current tenant (RLS filtered).

    Returns only pending reminders by default; pass include_dismissed=true for all.
    """
    stmt = select(Reminder)
    if not include_dismissed:
        stmt = stmt.where(Reminder.status == "pending")
    stmt = stmt.order_by(Reminder.remind_at)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    reminder_in: ReminderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = request.state.tenant_id
    reminder = Reminder(tenant_id=tenant_id, **reminder_in.model_dump())
    db.add(reminder)
    await db.flush()
    await db.refresh(reminder)

    logger.info(f"Recordatorio creado: {reminder.id} para tenant {tenant_id}")
    return reminder


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: UUID,
    reminder_in: ReminderUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update reminder status (e.g. dismiss it)."""
    stmt = select(Reminder).where(Reminder.id == reminder_id)
    reminder = (await db.execute(stmt)).scalar_one_or_none()

    if not reminder:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado")

    reminder.status = reminder_in.status
    await db.flush()
    await db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard delete — reminders are not clinical records."""
    stmt = select(Reminder).where(Reminder.id == reminder_id)
    reminder = (await db.execute(stmt)).scalar_one_or_none()

    if not reminder:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado")

    await db.delete(reminder)
    await db.flush()
    logger.info(f"Recordatorio eliminado: {reminder_id}")
