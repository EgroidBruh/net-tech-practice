"""Durable incident -> telephony HTTP delivery. Run with python -m notifications."""
import logging
import signal
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import UUID

import httpx
from sqlalchemy import select

from config import settings
from database import SessionLocal
from models.tables import IncidentRow, NotificationRow, EmployeeRow
from services import escalate_notification

logger = logging.getLogger(__name__)


def deliver(db, row, client):
    now = datetime.now(timezone.utc)
    try:
        if row.status == "PENDING":
            row.delivery_attempts += 1
            incident = db.get(IncidentRow, row.incident_id)
            response = client.post("/calls", json={
                "id": str(row.id), "incident_id": str(row.incident_id),
                "employee_id": str(row.employee_id), "employee_name": row.employee_name,
                "phone_number": row.phone_number, "sip_extension": row.sip_extension,
                "title": incident.title, "description": incident.description,
                "severity": incident.severity,
            })
        else:
            response = client.get(f"/calls/{row.id}")
        response.raise_for_status()
        data = response.json()
        if UUID(data["id"]) != row.id:
            raise ValueError("Unexpected call ID")
        status = data["status"]
        if status not in {"QUEUED", "DIALING", "RINGING", "ANSWERED", "NO_ANSWER", "BUSY", "FAILED", "UNKNOWN", "CONFIRMED", "UNCONFIRMED"}:
            raise ValueError("Unexpected call status")
        row.status = status
        row.hangup_cause = data.get("hangup_cause")
        row.last_error = data.get("last_error")
        row.answered_at = datetime.fromisoformat(data["answered_at"]) if data.get("answered_at") else None
        row.finished_at = datetime.fromisoformat(data["finished_at"]) if data.get("finished_at") else None
        row.confirmed_at = datetime.fromisoformat(data["confirmed_at"]) if data.get("confirmed_at") else None
        row.dtmf_digit = data.get("dtmf_digit")
        if row.finished_at:
            escalate_notification(db, row)
        row.next_attempt_at = now + timedelta(seconds=settings.notification_poll_interval)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        # Repeating POST is safe: the telephony service persists the same UUID.
        row.last_error = f"Телефонный сервис недоступен: {type(exc).__name__}"
        row.next_attempt_at = now + timedelta(seconds=min(60, 2 ** min(row.delivery_attempts, 6)))
        logger.warning("Notification %s: %s", row.id, row.last_error)
    row.updated_at = now


def synchronize_directory(client, session_factory=SessionLocal):
    with session_factory() as db:
        users = [{"employee_id": str(e.id), "sip_extension": e.sip_extension}
                 for e in db.scalars(select(EmployeeRow).where(EmployeeRow.sip_extension.is_not(None)))]
    client.put("/directory", json=users).raise_for_status()


def process_batch(session_factory=SessionLocal, client=None):
    with session_factory() as db:
        ids = list(db.scalars(select(NotificationRow.id).where(
            NotificationRow.finished_at.is_(None),
            NotificationRow.next_attempt_at <= datetime.now(timezone.utc),
        ).order_by(NotificationRow.created_at).limit(50)))
    for notification_id in ids:
        with session_factory() as db:
            row = db.scalar(select(NotificationRow).where(
                NotificationRow.id == notification_id,
                NotificationRow.finished_at.is_(None),
                NotificationRow.next_attempt_at <= datetime.now(timezone.utc),
            ).with_for_update(skip_locked=True))
            if row:
                deliver(db, row, client)
                db.commit()


def main():
    logging.basicConfig(level=logging.INFO)
    stop = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    with httpx.Client(base_url=settings.telephony_url, headers={"Authorization": f"Bearer {settings.telephony_token}"}, timeout=settings.telephony_http_timeout) as client:
        last_sync = 0
        import time
        while not stop.is_set():
            try:
                if time.monotonic() - last_sync >= 1:
                    synchronize_directory(client)
                    last_sync = time.monotonic()
                process_batch(client=client)
            except Exception:
                logger.exception("Notification delivery failed; will retry")
            stop.wait(settings.notification_poll_interval)


if __name__ == "__main__":
    main()
