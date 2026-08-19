"""API v1 — Médico favoritos (Fase 13).

Reusable snippets (diagnosis / plan / indication / prescription) that speed up
documentation. Tenant-scoped via RLS (tenant_id from the JWT only). Favorites are
editable preferences, not clinical evidence, so update and hard delete are allowed.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.medico_favorito import MedicoFavorito
from app.schemas.medico_favorito import (
    FavoritoKind,
    MedicoFavoritoCreate,
    MedicoFavoritoResponse,
    MedicoFavoritoUpdate,
)

logger = logging.getLogger("medrecord.favoritos")
router = APIRouter()


@router.get("/", response_model=List[MedicoFavoritoResponse])
async def list_favoritos(
    request: Request,
    kind: FavoritoKind | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List the tenant's favorites (RLS filtered), optionally by kind."""
    stmt = select(MedicoFavorito)
    if kind is not None:
        stmt = stmt.where(MedicoFavorito.kind == kind)
    stmt = stmt.order_by(MedicoFavorito.label)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=MedicoFavoritoResponse, status_code=status.HTTP_201_CREATED)
async def create_favorito(
    favorito_in: MedicoFavoritoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = request.state.tenant_id
    favorito = MedicoFavorito(
        tenant_id=tenant_id,
        creado_por=tenant_id,
        **favorito_in.model_dump(),
    )
    db.add(favorito)
    await db.flush()
    await db.refresh(favorito)
    logger.info("Favorito creado: %s (%s) tenant %s", favorito.id, favorito.kind, tenant_id)
    return favorito


@router.put("/{favorito_id}", response_model=MedicoFavoritoResponse)
async def update_favorito(
    favorito_id: UUID,
    favorito_in: MedicoFavoritoUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    favorito = (
        await db.execute(select(MedicoFavorito).where(MedicoFavorito.id == favorito_id))
    ).scalar_one_or_none()
    if favorito is None:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    favorito.label = favorito_in.label
    favorito.texto = favorito_in.texto
    favorito.modificado_en = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(favorito)
    return favorito


@router.delete("/{favorito_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorito(
    favorito_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    favorito = (
        await db.execute(select(MedicoFavorito).where(MedicoFavorito.id == favorito_id))
    ).scalar_one_or_none()
    if favorito is None:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    await db.delete(favorito)
    await db.flush()
