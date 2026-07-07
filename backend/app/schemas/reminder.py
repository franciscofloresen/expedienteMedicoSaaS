from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReminderCreate(BaseModel):
    paciente_id: Optional[UUID] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    remind_at: datetime

    @field_validator("remind_at")
    @classmethod
    def remind_at_must_be_future(cls, v: datetime) -> datetime:
        now = datetime.now(v.tzinfo) if v.tzinfo else datetime.now()
        if v <= now:
            raise ValueError("remind_at debe ser una fecha futura")
        return v


class ReminderUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|dismissed)$")


class ReminderResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    paciente_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    remind_at: datetime
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
