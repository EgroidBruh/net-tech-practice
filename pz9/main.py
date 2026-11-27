from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routes.create_employee import router as employees_router
from routes.current_duty import router as duty_router
from routes.register_incident import router as incidents_router
from routes.web import router as web_router
from admin import setup_admin

app = FastAPI(title="Сервис дежурств и телефонного оповещения", version="0.3.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(employees_router)
app.include_router(duty_router)
app.include_router(incidents_router)
app.include_router(web_router)
admin = setup_admin(app)
