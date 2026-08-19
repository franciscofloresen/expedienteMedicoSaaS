from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Categoria = Literal["antes", "despues", "seguimiento", "general"]
Lateralidad = Literal["izquierda", "derecha", "bilateral", "na"]


class FotografiaCreate(BaseModel):
    paciente_id: UUID
    clinical_file_id: UUID
    consentimiento_id: UUID | None = None
    categoria: Categoria = "general"
    lateralidad: Lateralidad | None = None
    zona_anatomica: str | None = Field(None, max_length=120)
    fecha_toma: date | None = None
    grupo_comparacion: str | None = Field(None, max_length=80)


class FotografiaUpdate(BaseModel):
    consentimiento_id: UUID | None = None
    categoria: Categoria = "general"
    lateralidad: Lateralidad | None = None
    zona_anatomica: str | None = Field(None, max_length=120)
    fecha_toma: date | None = None
    grupo_comparacion: str | None = Field(None, max_length=80)


class FotografiaResponse(BaseModel):
    id: UUID
    paciente_id: UUID
    clinical_file_id: UUID
    consentimiento_id: UUID | None = None
    categoria: str
    lateralidad: str | None = None
    zona_anatomica: str | None = None
    fecha_toma: date | None = None
    grupo_comparacion: str | None = None
    creado_en: datetime
    modificado_en: datetime

    model_config = ConfigDict(from_attributes=True)
