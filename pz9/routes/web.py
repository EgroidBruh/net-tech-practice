from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from uuid import UUID
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from config import settings
from database import get_db
from models.create_employee import EmployeeCreate, Role
from models.current_duty import ShiftCreate, DefaultDuty
from models.register_incident import IncidentCreate, Severity
from models.tables import EmployeeRow, ShiftRow, IncidentRow, IncidentEventRow, DefaultDutyRow, NotificationRow
import services

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
zone = ZoneInfo(settings.ui_timezone)
templates.env.filters["localtime"] = lambda value: value.astimezone(zone).strftime("%d.%m.%Y %H:%M")

def render(request, db, page, error=None, values=None, status_code=200):
    employees = db.scalars(select(EmployeeRow).order_by(EmployeeRow.last_name)).all()
    shifts = db.scalars(select(ShiftRow).order_by(ShiftRow.start_time.desc())).all()
    incidents = db.scalars(select(IncidentRow).order_by(IncidentRow.created_at.desc())).all()
    try:
        current = services.current_duty(db)
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        current = None
    default = db.get(DefaultDutyRow, 1)
    return templates.TemplateResponse(request=request, name=page+".html", context=dict(
        page=page, employees=employees, shifts=shifts, incidents=incidents,
        employee_map={e.id: e for e in employees}, current=current,
        default_id=default.employee_id if default else None, roles=Role, severities=Severity,
        timezone=settings.ui_timezone, error=error, values=values or {},
        saved=request.query_params.get("saved") == "1"), status_code=status_code)

@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    return render(request, db, "home")

@router.get("/ui/{page}")
def page_view(page: str, request: Request, db: Session = Depends(get_db)):
    if page not in {"employees", "duty", "incidents"}:
        raise HTTPException(404)
    return render(request, db, page)

# Forms and JSON endpoints share validation and business logic.
@router.post("/ui/{action}")
async def submit(action: str, request: Request, db: Session = Depends(get_db)):
    actions = {"employees": (EmployeeCreate, services.create_employee, "employees"),
               "shifts": (ShiftCreate, services.create_shift, "duty"),
               "default": (DefaultDuty, services.set_default, "duty"),
               "incidents": (IncidentCreate, services.create_incident, "incidents")}
    if action not in actions:
        raise HTTPException(404)
    schema, save, page = actions[action]
    values = dict(await request.form())
    def process():
        data = values.copy()
        try:
            if action == "employees" and not data.get("middle_name", "").strip():
                data["middle_name"] = None
            if action == "employees" and not data.get("sip_extension", "").strip():
                data["sip_extension"] = None
            if action == "shifts":
                for field in ("start_time", "end_time"):
                    parsed = datetime.fromisoformat(data.get(field, ""))
                    data[field] = parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed
            save(db, schema.model_validate(data))
        except (ValidationError, ValueError, HTTPException) as exc:
            db.rollback()
            if isinstance(exc, HTTPException):
                message, status = str(exc.detail), exc.status_code
            elif isinstance(exc, ValidationError):
                message = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
                status = 422
            else:
                message, status = "Проверьте дату и время смены", 422
            return render(request, db, page, message, values, status)
        return RedirectResponse(f"/ui/{page}?saved=1", status_code=303)
    return await run_in_threadpool(process)

@router.get("/ui/incidents/{incident_id}")
def incident_detail(incident_id: UUID, request: Request, db: Session = Depends(get_db)):
    row = services.incident(db, incident_id)
    events = db.scalars(select(IncidentEventRow).where(IncidentEventRow.incident_id == incident_id)).all()
    calls = db.scalars(select(NotificationRow).where(NotificationRow.incident_id == incident_id).order_by(NotificationRow.created_at)).all()
    return templates.TemplateResponse(request=request, name="detail.html", context=dict(page="incidents", incident=row, events=events, calls=calls, timezone=settings.ui_timezone))
