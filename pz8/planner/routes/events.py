from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from planner.database.connection import as_record, get_database, next_id
from planner.models.events import EventCreate, EventRead, EventUpdate

event_router = APIRouter(tags=["Events"])
DatabaseDep = Annotated[Database, Depends(get_database)]
EventId = Annotated[int, Path(gt=0)]


def event_or_404(document: dict | None) -> dict:
    if document is None:
        raise HTTPException(404, "Event with supplied ID does not exist")
    return as_record(document)


@event_router.get("/", response_model=list[EventRead])
def retrieve_all_events(database: DatabaseDep):
    return [as_record(event) for event in database.events.find().sort("_id", 1)]


@event_router.get("/{id}", response_model=EventRead)
def retrieve_event(id: EventId, database: DatabaseDep):
    return event_or_404(database.events.find_one({"_id": id}))


@event_router.post("/new")
def create_event(body: EventCreate, database: DatabaseDep):
    event_id = body.id
    if event_id is None:
        event_id = next_id(database, "events")
    else:
        # Future generated IDs must stay above manually supplied IDs.
        database.counters.update_one(
            {"_id": "events"}, {"$max": {"value": event_id}}, upsert=True,
        )
    try:
        database.events.insert_one({"_id": event_id, **body.model_dump(exclude={"id"})})
    except DuplicateKeyError:
        raise HTTPException(409, "Event with supplied ID already exists") from None
    return {"message": "Event created successfully", "id": event_id}


@event_router.put("/edit/{id}", response_model=EventRead)
@event_router.put("/{id}", response_model=EventRead, include_in_schema=False)
def update_event(id: EventId, body: EventUpdate, database: DatabaseDep):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return retrieve_event(id, database)
    return event_or_404(database.events.find_one_and_update(
        {"_id": id}, {"$set": changes}, return_document=ReturnDocument.AFTER,
    ))


@event_router.delete("/delete/{id}")
@event_router.delete("/{id}", include_in_schema=False)
def delete_event(id: EventId, database: DatabaseDep):
    if database.events.delete_one({"_id": id}).deleted_count == 0:
        raise HTTPException(404, "Event with supplied ID does not exist")
    return {"message": "Event deleted successfully"}


@event_router.delete("/")
def delete_all_events(database: DatabaseDep):
    database.events.delete_many({})
    return {"message": "Events deleted successfully"}
