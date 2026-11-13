from uuid import UUID
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from database import get_db
from models.create_employee import Employee, EmployeeCreate, EmployeePatch
from models.tables import EmployeeRow
import services
router = APIRouter(prefix="/employees", tags=["Сотрудники"])

@router.post("", response_model=Employee, status_code=201)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    return services.create_employee(db, data)

@router.get("", response_model=list[Employee])
def list_employees(db: Session = Depends(get_db)):
    return db.scalars(select(EmployeeRow).order_by(EmployeeRow.created_at)).all()

@router.get("/{employee_id}", response_model=Employee)
def get_employee(employee_id: UUID, db: Session = Depends(get_db)):
    return services.employee(db, employee_id)

@router.patch("/{employee_id}", response_model=Employee)
def update_employee(employee_id: UUID, data: EmployeePatch, db: Session = Depends(get_db)):
    return services.update_employee(db, employee_id, data)

@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: UUID, db: Session = Depends(get_db)):
    services.delete_employee(db, employee_id)
    return Response(status_code=204)
