from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: UUID = Field(description="Ключ идемпотентности: повтор запроса не создаёт второй звонок")
    incident_id: UUID
    employee_id: UUID
    employee_name: str = Field(min_length=1, max_length=302)
    phone_number: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    sip_extension: str = Field(pattern=r"^[0-9]{2,10}$")
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    severity: Literal["INFO", "WARNING", "CRITICAL"]


class Call(CallRequest):
    status: Literal["QUEUED", "DIALING", "RINGING", "ANSWERED", "NO_ANSWER", "BUSY", "FAILED", "UNKNOWN", "CONFIRMED", "UNCONFIRMED"]
    created_at: datetime
    updated_at: datetime
    answered_at: datetime | None = None
    confirmed_at: datetime | None = None
    dtmf_digit: str | None = None
    finished_at: datetime | None = None
    hangup_cause: str | None = None
    last_error: str | None = None
