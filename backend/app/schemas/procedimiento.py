from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Checklist ──
class ChecklistItem(BaseModel):
    texto: str = Field(..., min_length=1)
    completado: bool = False


class ChecklistCreate(BaseModel):
    paciente_id: UUID
    encuentro_id: UUID | None = None
    momento: Literal["pre", "post"]
    items: list[ChecklistItem] = Field(default_factory=list)
    observaciones: str | None = None


class ChecklistUpdate(BaseModel):
    items: list[ChecklistItem]
    observaciones: str | None = None


class ChecklistResponse(BaseModel):
    id: UUID
    paciente_id: UUID
    encuentro_id: UUID | None = None
    momento: str
    items: list[ChecklistItem]
    observaciones: str | None = None
    creado_en: datetime
    modificado_en: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Adverse event ──
class EventoAdversoCreate(BaseModel):
    paciente_id: UUID
    encuentro_id: UUID | None = None
    descripcion: str = Field(..., min_length=1)
    severidad: Literal["leve", "moderado", "grave"] = "leve"
    fecha: date | None = None
    manejo: str | None = None


class EventoAdversoUpdate(BaseModel):
    descripcion: str = Field(..., min_length=1)
    severidad: Literal["leve", "moderado", "grave"]
    fecha: date | None = None
    manejo: str | None = None
    estado: Literal["abierto", "resuelto"]


class EventoAdversoResponse(BaseModel):
    id: UUID
    paciente_id: UUID
    encuentro_id: UUID | None = None
    descripcion: str
    severidad: str
    fecha: date | None = None
    manejo: str | None = None
    estado: str
    creado_en: datetime
    modificado_en: datetime

    model_config = ConfigDict(from_attributes=True)
