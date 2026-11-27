"""The telephone service owns its durable SQLite queue and call history."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class CallConflict(Exception):
    pass


class CallStore:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS calls (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                answered_at TEXT, finished_at TEXT, hangup_cause TEXT, last_error TEXT
            )""")
            columns = {r[1] for r in db.execute("PRAGMA table_info(calls)")}
            for name in ("confirmed_at", "dtmf_digit"):
                if name not in columns:
                    db.execute(f"ALTER TABLE calls ADD COLUMN {name} TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS ix_calls_queue ON calls(status, created_at)")

    def decode(self, row):
        if row is None:
            return None
        values = dict(row)
        payload = json.loads(values.pop("payload"))
        return {**payload, **values}

    def get(self, call_id):
        with self.connection() as db:
            return self.decode(db.execute("SELECT * FROM calls WHERE id=?", (str(call_id),)).fetchone())

    def create(self, request):
        payload = json.dumps(request.model_dump(mode="json"), sort_keys=True)
        now = timestamp()
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO calls(id,payload,status,created_at,updated_at) VALUES(?,?,'QUEUED',?,?)", (str(request.id), payload, now, now))
            row = db.execute("SELECT * FROM calls WHERE id=?", (str(request.id),)).fetchone()
            if row["payload"] != payload:
                raise CallConflict("Этот id уже использован для другого запроса")
            return self.decode(row)

    def update(self, call_id, **values):
        allowed = {"status", "answered_at", "finished_at", "hangup_cause", "last_error", "confirmed_at", "dtmf_digit"}
        if not values.keys() <= allowed:
            raise ValueError("Unexpected call fields")
        values["updated_at"] = timestamp()
        with self.connection() as db:
            db.execute(f"UPDATE calls SET {', '.join(f'{key}=?' for key in values)} WHERE id=?", (*values.values(), str(call_id)))

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM calls WHERE status='QUEUED' ORDER BY created_at LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE calls SET status='DIALING', updated_at=? WHERE id=?", (timestamp(), row["id"]))
            return self.decode(row)

    def recover(self):
        # A command may already have reached FreeSWITCH before a crash. Never
        # redial such a call automatically; preserve the uncertainty for review.
        with self.connection() as db:
            now = timestamp()
            db.execute("""UPDATE calls SET status=CASE WHEN confirmed_at IS NOT NULL THEN 'CONFIRMED' ELSE 'UNKNOWN' END,
                finished_at=?, updated_at=?, last_error='Телефонный сервис перезапущен во время звонка'
                WHERE status IN ('DIALING','RINGING','ANSWERED','CONFIRMED') AND finished_at IS NULL""", (now, now))
