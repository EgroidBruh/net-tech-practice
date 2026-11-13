from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db
from models.register_incident import Incident, IncidentCreate, IncidentCreatedEvent, IncidentPatch
from models.tables import IncidentRow, IncidentEventRow
import services
router = APIRouter(prefix="/incidents", tags=["Инциденты"])

@router.post("", response_model=Incident, status_code=201)
def register_incident(data: IncidentCreate, db: Session = Depends(get_db)):
    return services.create_incident(db, data)

@router.get("", response_model=list[Incident])
def list_incidents(db: Session = Depends(get_db)):
    return db.scalars(select(IncidentRow).order_by(IncidentRow.created_at)).all()

@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: UUID, db: Session = Depends(get_db)):
    return services.incident(db, incident_id)

@router.patch("/{incident_id}", response_model=Incident)
def update_incident(incident_id: UUID, data: IncidentPatch, db: Session = Depends(get_db)):
    return services.update_incident(db, incident_id, data)

@router.delete("/{incident_id}", status_code=204)
def delete_incident(incident_id: UUID, db: Session = Depends(get_db)):
    services.delete_incident(db, incident_id)
    return Response(status_code=204)

@router.get("/{incident_id}/events", response_model=list[IncidentCreatedEvent])
def list_incident_events(incident_id: UUID, db: Session = Depends(get_db)):
    services.incident(db, incident_id)
    return db.scalars(select(IncidentEventRow).where(IncidentEventRow.incident_id == incident_id).order_by(IncidentEventRow.occurred_at)).all()
