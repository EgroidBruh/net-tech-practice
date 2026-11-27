from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Notification(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    incident_id: UUID
    employee_id: UUID | None
    employee_name: str | None
    phone_number: str | None
    sip_extension: str | None
    duty_source: str | None
    parent_id: UUID | None = None
    confirmed_at: datetime | None = None
    dtmf_digit: str | None = None
    status: str
    delivery_attempts: int
    last_error: str | None
    hangup_cause: str | None
    created_at: datetime
    updated_at: datetime
    answered_at: datetime | None
    finished_at: datetime | None
