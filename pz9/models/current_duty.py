from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator
from models.patch import PatchModel


class ShiftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UUID
    start_time: AwareDatetime
    end_time: AwareDatetime

    @model_validator(mode="after")
    def valid_interval(self):
        if self.end_time <= self.start_time:
            raise ValueError("Конец смены должен быть позже начала")
        return self


class Shift(ShiftCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class ShiftPatch(PatchModel):
    employee_id: UUID | None = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None


class DefaultDuty(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: UUID


class CurrentDuty(BaseModel):
    employee_id: UUID
    name: str
    phone_number: str
    sip_extension: str | None = None
    source: Literal["schedule", "default"]
    resolved_at: datetime
