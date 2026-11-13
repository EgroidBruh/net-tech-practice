"""MongoDB connection and atomic counters for the existing numeric API IDs."""

import os

from fastapi import Request
from pymongo import MongoClient, ReturnDocument
from pymongo.database import Database


def make_client(database_url: str | None = None) -> MongoClient:
    return MongoClient(
        database_url or os.getenv("DATABASE_URL", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
    )


def conn(client: MongoClient, database_name: str | None = None) -> Database:
    client.admin.command("ping")
    database = client[database_name or os.getenv("DATABASE_NAME", "planner")]
    database.users.create_index("email", unique=True)
    return database


def get_database(request: Request) -> Database:
    return request.app.state.database


def next_id(database: Database, collection: str) -> int:
    counter = database.counters.find_one_and_update(
        {"_id": collection}, {"$inc": {"value": 1}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    return counter["value"]


def as_record(document: dict) -> dict:
    record = document.copy()
    record["id"] = record.pop("_id")
    return record
