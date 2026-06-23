from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CitaBase(BaseModel):
    paciente_id: Optional[UUID] = None
    titulo: str = Field(..., max_length=200)
    fecha_inicio: datetime
    fecha_fin: datetime
    estado: str = Field(default="Programada", max_length=50)
    notas: Optional[str] = None

class CitaCreate(CitaBase):
    pass

class CitaUpdate(BaseModel):
    paciente_id: Optional[UUID] = None
    titulo: Optional[str] = Field(None, max_length=200)
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    estado: Optional[str] = Field(None, max_length=50)
    notas: Optional[str] = None

class CitaResponse(CitaBase):
    id: UUID
    tenant_id: UUID
    creado_en: datetime
    modificado_en: datetime

    model_config = ConfigDict(from_attributes=True)
