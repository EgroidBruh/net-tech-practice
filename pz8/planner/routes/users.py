from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from planner.database.connection import as_record, get_database, next_id
from planner.models.users import NewUser, UserRead, UserSignIn, UserUpdate
from planner.security import hash_password, verify_password

user_router = APIRouter(tags=["User"])
DatabaseDep = Annotated[Database, Depends(get_database)]
UserId = Annotated[int, Path(gt=0)]


def user_or_404(document: dict | None) -> dict:
    if document is None:
        raise HTTPException(404, "User with supplied ID does not exist")
    return as_record(document)


def create_user_record(data: NewUser, database: Database) -> dict:
    user = {
        "_id": next_id(database, "users"),
        "email": str(data.email), "password_hash": hash_password(data.password),
        "events": [event.model_dump() for event in data.events],
    }
    try:
        database.users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(409, "User with supplied email exists") from None
    return as_record(user)


@user_router.post("/signup")
def sign_new_user(data: NewUser, database: DatabaseDep) -> dict[str, str]:
    create_user_record(data, database)
    return {"message": "User successfully registered!"}


@user_router.post("/signin")
def sign_user_in(data: UserSignIn, database: DatabaseDep) -> dict[str, str]:
    user = database.users.find_one({"email": str(data.email)})
    if user is None:
        raise HTTPException(404, "User does not exist")
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(403, "Wrong credentials passed")
    return {"message": "User signed in successfully"}


@user_router.post("/new", response_model=UserRead)
@user_router.post("/", response_model=UserRead, include_in_schema=False)
def create_user(data: NewUser, database: DatabaseDep):
    return create_user_record(data, database)


@user_router.get("/", response_model=list[UserRead])
def retrieve_all_users(database: DatabaseDep):
    return [as_record(user) for user in database.users.find().sort("_id", 1)]


@user_router.get("/{id}", response_model=UserRead)
def retrieve_user(id: UserId, database: DatabaseDep):
    return user_or_404(database.users.find_one({"_id": id}))


@user_router.put("/edit/{id}", response_model=UserRead)
@user_router.put("/{id}", response_model=UserRead, include_in_schema=False)
def update_user(id: UserId, body: UserUpdate, database: DatabaseDep):
    changes = body.model_dump(exclude_unset=True)
    if "password" in changes:
        changes["password_hash"] = hash_password(changes.pop("password"))
    if not changes:
        return retrieve_user(id, database)
    try:
        user = database.users.find_one_and_update(
            {"_id": id}, {"$set": changes}, return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        raise HTTPException(409, "User with supplied email exists") from None
    return user_or_404(user)


@user_router.delete("/delete/{id}")
@user_router.delete("/{id}", include_in_schema=False)
def delete_user(id: UserId, database: DatabaseDep):
    if database.users.delete_one({"_id": id}).deleted_count == 0:
        raise HTTPException(404, "User with supplied ID does not exist")
    return {"message": "User deleted successfully"}
