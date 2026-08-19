from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlantillaCampos(BaseModel):
    """The pre-fillable note fields. `extra="forbid"` keeps templates a limited,
    versioned configuration — NOT a generic form builder (Fase 13)."""

    motivo_consulta: str | None = None
    exploracion_fisica: str | None = None
    plan_tratamiento: str | None = None
    diagnostico: str | None = None

    model_config = ConfigDict(extra="forbid")


class NotaPlantillaCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    campos: PlantillaCampos


class NotaPlantillaUpdate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    campos: PlantillaCampos


class NotaPlantillaResponse(BaseModel):
    id: UUID
    nombre: str
    # The stored JSON as-is (only the fields the doctor set), so the client gets
    # exactly what to pre-fill without null placeholders.
    campos: dict[str, str]
    version: int
    creado_en: datetime
    modificado_en: datetime

    model_config = ConfigDict(from_attributes=True)
