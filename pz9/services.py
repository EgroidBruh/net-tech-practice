from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, or_, text, delete
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from models.tables import EmployeeRow, ShiftRow, DefaultDutyRow, IncidentRow, IncidentEventRow
from models.current_duty import CurrentDuty, ShiftCreate
from models.create_employee import Role, EmployeeCreate

def lock(db, key):
    # Transaction-scoped locks serialize cross-column phone and interval checks
    # across all app workers. SQLite is used only by isolated unit tests.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Конфликт данных")

def employee(db, employee_id):
    row = db.get(EmployeeRow, employee_id)
    if row is None:
        raise HTTPException(404, "Сотрудник не найден")
    return row

def create_employee(db, data):
    lock(db, 71001)
    if db.scalar(select(EmployeeRow.id).where(EmployeeRow.email == data.email)):
        raise HTTPException(409, "Email уже зарегистрирован")
    phones = [data.work_phone, data.mobile_phone]
    if db.scalar(select(EmployeeRow.id).where(or_(EmployeeRow.work_phone.in_(phones), EmployeeRow.mobile_phone.in_(phones)))):
        raise HTTPException(409, "Телефон уже зарегистрирован")
    row = EmployeeRow(**data.model_dump())
    db.add(row)
    commit(db)
    return row

def create_shift(db, data):
    lock(db, 71002)
    employee(db, data.employee_id)
    # Preserve the original closed-interval semantics, including shared endpoints.
    existing = select(ShiftRow.id).where(ShiftRow.start_time <= data.end_time, ShiftRow.end_time >= data.start_time)
    if db.scalar(existing):
        raise HTTPException(409, "Смена пересекается с существующей")
    row = ShiftRow(**data.model_dump())
    db.add(row)
    commit(db)
    return row

def set_default(db, data):
    lock(db, 71002)
    row = employee(db, data.employee_id)
    if row.role != Role.SHIFT_LEAD:
        raise HTTPException(422, "Дежурный по умолчанию должен быть старшим смены (SHIFT_LEAD)")
    default = db.get(DefaultDutyRow, 1)
    if default:
        default.employee_id = row.id
    else:
        db.add(DefaultDutyRow(id=1, employee_id=row.id))
    commit(db)
    return data

def current_duty(db):
    now = datetime.now(timezone.utc)
    shift = db.scalar(select(ShiftRow).where(ShiftRow.start_time <= now, ShiftRow.end_time >= now))
    default = db.get(DefaultDutyRow, 1) if shift is None else None
    row = db.get(EmployeeRow, shift.employee_id if shift else default.employee_id) if shift or default else None
    if row is None:
        raise HTTPException(503, "Не найден ответственный специалист")
    return CurrentDuty(employee_id=row.id, name=" ".join(filter(None, [row.last_name, row.first_name, row.middle_name])), phone_number=row.mobile_phone, source="schedule" if shift else "default", resolved_at=now)

def create_incident(db, data):
    now = datetime.now(timezone.utc)
    row = IncidentRow(**data.model_dump(), created_at=now)
    db.add(row)
    db.flush()
    db.add(IncidentEventRow(incident_id=row.id, severity=row.severity, occurred_at=now))
    commit(db)  # Incident and its event are saved atomically.
    return row

def incident(db, incident_id):
    row = db.get(IncidentRow, incident_id)
    if row is None:
        raise HTTPException(404, "Инцидент не найден")
    return row


def merged_data(schema, row, patch):
    values = {name: getattr(row, name) for name in schema.model_fields}
    values.update(patch.model_dump(exclude_unset=True))
    try:
        return schema.model_validate(values)
    except ValidationError as exc:
        raise RequestValidationError([
            {**error, "loc": ("body", *error["loc"])} for error in exc.errors()
        ]) from exc


def update_employee(db, employee_id, patch):
    lock(db, 71001)
    lock(db, 71002)
    row = employee(db, employee_id)
    data = merged_data(EmployeeCreate, row, patch)
    if db.scalar(select(EmployeeRow.id).where(EmployeeRow.id != row.id, EmployeeRow.email == data.email)):
        raise HTTPException(409, "Email уже зарегистрирован")
    phones = [data.work_phone, data.mobile_phone]
    if db.scalar(select(EmployeeRow.id).where(EmployeeRow.id != row.id, or_(EmployeeRow.work_phone.in_(phones), EmployeeRow.mobile_phone.in_(phones)))):
        raise HTTPException(409, "Телефон уже зарегистрирован")
    default = db.get(DefaultDutyRow, 1)
    if default and default.employee_id == row.id and data.role != Role.SHIFT_LEAD:
        raise HTTPException(409, "Сначала измените дежурного по умолчанию")
    for name, value in data.model_dump().items():
        setattr(row, name, value)
    commit(db)
    return row


def delete_employee(db, employee_id):
    lock(db, 71001)
    lock(db, 71002)
    row = employee(db, employee_id)
    default = db.get(DefaultDutyRow, 1)
    if (default and default.employee_id == row.id) or db.scalar(select(ShiftRow.id).where(ShiftRow.employee_id == row.id)):
        raise HTTPException(409, "Сначала удалите смены и назначение дежурного по умолчанию")
    db.delete(row)
    commit(db)


def shift(db, shift_id):
    row = db.get(ShiftRow, shift_id)
    if row is None:
        raise HTTPException(404, "Смена не найдена")
    return row


def update_shift(db, shift_id, patch):
    lock(db, 71002)
    row = shift(db, shift_id)
    data = merged_data(ShiftCreate, row, patch)
    employee(db, data.employee_id)
    if db.scalar(select(ShiftRow.id).where(ShiftRow.id != row.id, ShiftRow.start_time <= data.end_time, ShiftRow.end_time >= data.start_time)):
        raise HTTPException(409, "Смена пересекается с существующей")
    for name, value in data.model_dump().items():
        setattr(row, name, value)
    commit(db)
    return row


def delete_shift(db, shift_id):
    lock(db, 71002)
    db.delete(shift(db, shift_id))
    commit(db)


def delete_default(db):
    lock(db, 71002)
    row = db.get(DefaultDutyRow, 1)
    if row is None:
        raise HTTPException(404, "Дежурный по умолчанию не назначен")
    db.delete(row)
    commit(db)


def locked_incident(db, incident_id):
    row = db.scalar(select(IncidentRow).where(IncidentRow.id == incident_id).with_for_update())
    if row is None:
        raise HTTPException(404, "Инцидент не найден")
    return row


def update_incident(db, incident_id, patch):
    row = locked_incident(db, incident_id)
    for name, value in patch.model_dump(exclude_unset=True).items():
        setattr(row, name, value)
    commit(db)
    return row


def delete_incident(db, incident_id):
    row = locked_incident(db, incident_id)
    db.execute(delete(IncidentEventRow).where(IncidentEventRow.incident_id == row.id))
    db.delete(row)
    commit(db)
