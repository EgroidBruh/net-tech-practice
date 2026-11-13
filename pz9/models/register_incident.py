from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from models.patch import PatchModel


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source: str = Field(min_length=1, max_length=100)
    error_code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    severity: Severity


class Incident(IncidentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime


class IncidentPatch(PatchModel):
    source: str | None = Field(default=None, min_length=1, max_length=100)
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    severity: Severity | None = None
    status: IncidentStatus | None = None


class IncidentCreatedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_type: Literal["IncidentCreatedEvent"] = "IncidentCreatedEvent"
    incident_id: UUID
    severity: Severity
    occurred_at: datetime
