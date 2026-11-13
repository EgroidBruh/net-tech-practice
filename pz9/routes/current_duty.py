from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db
from models.current_duty import CurrentDuty, DefaultDuty, Shift, ShiftCreate, ShiftPatch
from models.tables import ShiftRow
import services
router = APIRouter(prefix="/duty", tags=["Дежурства"])

@router.post("/shifts", response_model=Shift, status_code=201)
def create_shift(data: ShiftCreate, db: Session = Depends(get_db)):
    return services.create_shift(db, data)

@router.get("/shifts", response_model=list[Shift])
def list_shifts(db: Session = Depends(get_db)):
    return db.scalars(select(ShiftRow).order_by(ShiftRow.start_time)).all()

@router.patch("/shifts/{shift_id}", response_model=Shift)
def update_shift(shift_id: UUID, data: ShiftPatch, db: Session = Depends(get_db)):
    return services.update_shift(db, shift_id, data)

@router.delete("/shifts/{shift_id}", status_code=204)
def delete_shift(shift_id: UUID, db: Session = Depends(get_db)):
    services.delete_shift(db, shift_id)
    return Response(status_code=204)

@router.put("/default", response_model=DefaultDuty)
@router.patch("/default", response_model=DefaultDuty)
def set_default_duty(data: DefaultDuty, db: Session = Depends(get_db)):
    return services.set_default(db, data)

@router.delete("/default", status_code=204)
def delete_default_duty(db: Session = Depends(get_db)):
    services.delete_default(db)
    return Response(status_code=204)

@router.get("/current", response_model=CurrentDuty)
def get_current_duty(db: Session = Depends(get_db)):
    return services.current_duty(db)
