from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from model import Todo


todo_router = APIRouter()

todo_list: list[Todo] = []
templates = Jinja2Templates(directory=str(FilePath(__file__).parent / "templates"))

NOT_FOUND = "Егор, задача с указанным ID не найдена."


@todo_router.post("/todo", response_class=HTMLResponse)
async def add_todo(request: Request, todo: Todo = Depends(Todo.as_form)):
    todo.id = max((existing.id for existing in todo_list), default=0) + 1
    todo_list.append(todo)
    return templates.TemplateResponse(
        request=request, name="todo.html", context={"todos": todo_list}
    )


@todo_router.get("/todo", response_class=HTMLResponse)
async def retrieve_todos(request: Request):
    return templates.TemplateResponse(
        request=request, name="todo.html", context={"todos": todo_list}
    )


@todo_router.get("/todo/{todo_id}", response_class=HTMLResponse)
async def get_single_todo(
    request: Request,
    todo_id: int = Path(..., title="ID задачи")
):

    for todo in todo_list:
        if todo.id == todo_id:
            return templates.TemplateResponse(
                request=request, name="todo.html", context={"todo": todo}
            )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
