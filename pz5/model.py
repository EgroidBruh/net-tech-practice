from fastapi import Form
from pydantic import BaseModel


class Todo(BaseModel):
    id: int | None = None
    item: str

    @classmethod
    def as_form(cls, item: str = Form(..., min_length=1, pattern=r"\S")) -> "Todo":
        return cls(item=item.strip())
