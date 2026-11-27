import logging
import secrets
from contextlib import asynccontextmanager
from threading import Event, Thread
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from telephony.directory import DirectoryUser, reconcile
from telephony.config import TelephonySettings
from telephony.esl import ESLConnection, dial
from telephony.schemas import Call, CallRequest
from telephony.store import CallConflict, CallStore, timestamp

logger = logging.getLogger(__name__)
security = HTTPBearer()


def create_app(settings=None, store=None, run_worker=True):
    settings = settings or TelephonySettings()
    store = store or CallStore(settings.call_database)

    def authorize(credentials: HTTPAuthorizationCredentials = Depends(security)):
        if not secrets.compare_digest(credentials.credentials.encode(), settings.telephony_token.encode()):
            raise HTTPException(401, "Неверный токен телефонного сервиса")

    def worker(stop):
        while not stop.is_set():
            call = None
            try:
                call = store.claim()
                if call:
                    dial(call, store, settings, stop)
            except Exception:
                logger.exception("Call worker failed")
                if call:
                    store.update(call["id"], status="UNKNOWN", finished_at=timestamp(), last_error="Ошибка обработки звонка")
            stop.wait(0.5 if not call else 2)

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        stop = Event()
        thread = None
        if run_worker:
            store.recover()
            thread = Thread(target=worker, args=(stop,), daemon=True)
            thread.start()
        yield
        stop.set()
        if thread:
            thread.join(timeout=6)

    app = FastAPI(title="Телефонное оповещение через FreeSWITCH ESL", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready", dependencies=[Depends(authorize)])
    def ready():
        try:
            with ESLConnection(settings) as connection:
                connection.command("api status")
        except Exception as exc:
            raise HTTPException(503, "Нет подключения к FreeSWITCH ESL") from exc
        return {"status": "ok", "freeswitch": "connected"}

    directory_dirty = True

    @app.put("/directory", dependencies=[Depends(authorize)])
    def synchronize_directory(users: list[DirectoryUser]):
        nonlocal directory_dirty
        try:
            directory_dirty = reconcile(settings.sip_directory, users) or directory_dirty
            if not directory_dirty:
                return {"users": len(users)}
            with ESLConnection(settings) as connection:
                result = connection.command("api reloadxml")
                if not result.startswith("+OK"):
                    raise ValueError("FreeSWITCH rejected reloadxml")
            directory_dirty = False
        except Exception as exc:
            raise HTTPException(503, "Не удалось обновить SIP-каталог") from exc
        return {"users": len(users)}

    @app.post("/calls", response_model=Call, status_code=202, dependencies=[Depends(authorize)])
    def create_call(data: CallRequest):
        try:
            return store.create(data)
        except CallConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/calls/{call_id}", response_model=Call, dependencies=[Depends(authorize)])
    def get_call(call_id: UUID):
        call = store.get(call_id)
        if call is None:
            raise HTTPException(404, "Звонок не найден")
        return call

    return app


app = create_app()
