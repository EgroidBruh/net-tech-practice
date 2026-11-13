from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from sqlmodel import Column, Field as SQLField, JSON, SQLModel

from planner.models.events import EventRead


class User(BaseModel):
    email: EmailStr
    events: list[EventRead] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "fastapi@packt.com", "events": []}
        }
    )


class NewUser(User):
    password: str = Field(min_length=1, repr=False)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "fastapi@packt.com",
                "password": "Stro0ng!",
                "events": [],
            }
        }
    )


class UserRead(User):
    id: int

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=1, repr=False)
    events: list[EventRead] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Omit unchanged fields instead of sending null")
        return value


class UserSignIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, repr=False)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "fastapi@packt.com", "password": "Stro0ng!"}
        }
    )


class UserRecord(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = SQLField(default=None, primary_key=True)
    email: str = SQLField(unique=True, index=True)
    password_hash: str
    events: list[dict] = SQLField(default_factory=list, sa_column=Column(JSON, nullable=False))
