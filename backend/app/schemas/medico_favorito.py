from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FavoritoKind = Literal["diagnostico", "plan", "indicacion", "receta"]


class MedicoFavoritoCreate(BaseModel):
    kind: FavoritoKind
    label: str = Field(..., min_length=1, max_length=120)
    texto: str = Field(..., min_length=1)


class MedicoFavoritoUpdate(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    texto: str = Field(..., min_length=1)


class MedicoFavoritoResponse(BaseModel):
    id: UUID
    kind: FavoritoKind
    label: str
    texto: str
    creado_en: datetime
    modificado_en: datetime

    model_config = ConfigDict(from_attributes=True)
