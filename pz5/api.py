from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from todo import todo_router


app = FastAPI(
    title="Список задач — шаблоны Jinja2"
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
async def welcome() -> RedirectResponse:
    return RedirectResponse(url="/todo")


app.include_router(todo_router)
