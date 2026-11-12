from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from planner.database.connection import get_session
from planner.models.users import NewUser, UserRead, UserRecord, UserSignIn, UserUpdate
from planner.security import hash_password, verify_password

user_router = APIRouter(tags=["User"])
SessionDep = Annotated[Session, Depends(get_session)]
UserId = Annotated[int, Path(gt=0)]


def find_user(session: Session, id: int) -> UserRecord:
    user = session.get(UserRecord, id)
    if user is None:
        raise HTTPException(404, "User with supplied ID does not exist")
    return user


def commit_user(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "User with supplied email exists") from None


def create_user_record(data: NewUser, session: Session) -> UserRecord:
    user = UserRecord(
        email=str(data.email), password_hash=hash_password(data.password),
        events=[event.model_dump() for event in data.events],
    )
    session.add(user)
    commit_user(session)
    session.refresh(user)
    return user


@user_router.post("/signup")
def sign_new_user(data: NewUser, session: SessionDep) -> dict[str, str]:
    create_user_record(data, session)
    return {"message": "User successfully registered!"}


@user_router.post("/signin")
def sign_user_in(data: UserSignIn, session: SessionDep) -> dict[str, str]:
    user = session.exec(select(UserRecord).where(UserRecord.email == str(data.email))).first()
    if user is None:
        raise HTTPException(404, "User does not exist")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(403, "Wrong credentials passed")
    return {"message": "User signed in successfully"}


@user_router.post("/new", response_model=UserRead)
@user_router.post("/", response_model=UserRead, include_in_schema=False)
def create_user(data: NewUser, session: SessionDep):
    return create_user_record(data, session)


@user_router.get("/", response_model=list[UserRead])
def retrieve_all_users(session: SessionDep):
    return session.exec(select(UserRecord).order_by(UserRecord.id)).all()


@user_router.get("/{id}", response_model=UserRead)
def retrieve_user(id: UserId, session: SessionDep):
    return find_user(session, id)


@user_router.put("/edit/{id}", response_model=UserRead)
@user_router.put("/{id}", response_model=UserRead, include_in_schema=False)
def update_user(id: UserId, body: UserUpdate, session: SessionDep):
    user = find_user(session, id)
    for key, value in body.model_dump(exclude_unset=True).items():
        if key == "password":
            user.password_hash = hash_password(value)
        else:
            setattr(user, key, value)
    session.add(user)
    commit_user(session)
    session.refresh(user)
    return user


@user_router.delete("/delete/{id}")
@user_router.delete("/{id}", include_in_schema=False)
def delete_user(id: UserId, session: SessionDep):
    user = find_user(session, id)
    session.delete(user)
    session.commit()
    return {"message": "User deleted successfully"}
