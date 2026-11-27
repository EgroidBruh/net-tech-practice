from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, ForeignKey, CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator
from database import Base

class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return value.astimezone(timezone.utc) if value else None
    def process_result_value(self, value, dialect):
        if value and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

def now():
    return datetime.now(timezone.utc)

class EmployeeRow(Base):
    __tablename__ = "employees"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    position: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20))
    work_phone: Mapped[str] = mapped_column(String(16), unique=True)
    mobile_phone: Mapped[str] = mapped_column(String(16), unique=True)
    sip_extension: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    __table_args__ = (CheckConstraint("work_phone <> mobile_phone"),)

class ShiftRow(Base):
    __tablename__ = "shifts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime())
    __table_args__ = (CheckConstraint("end_time > start_time"),)

class DefaultDutyRow(Base):
    __tablename__ = "default_duty"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"))
    __table_args__ = (CheckConstraint("id = 1"),)

class IncidentRow(Base):
    __tablename__ = "incidents"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(100))
    error_code: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)

class IncidentEventRow(Base):
    __tablename__ = "incident_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(50), default="IncidentCreatedEvent")
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)


class NotificationRow(Base):
    """Transactional outbox and a local copy of the telephone service's result."""
    __tablename__ = "notifications"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    employee_id: Mapped[UUID | None] = mapped_column()
    employee_name: Mapped[str | None] = mapped_column(String(302))
    phone_number: Mapped[str | None] = mapped_column(String(16))
    sip_extension: Mapped[str | None] = mapped_column(String(10))
    parent_id: Mapped[UUID | None] = mapped_column(unique=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    dtmf_digit: Mapped[str | None] = mapped_column(String(1))
    duty_source: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    delivery_attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    hangup_cause: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now, index=True)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
