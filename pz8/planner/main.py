from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from planner.database.connection import conn, make_client
from planner.routes.events import event_router
from planner.routes.users import user_router


async def index() -> RedirectResponse:
    return RedirectResponse("/docs")


def create_app(database_url: str | None = None, database_name: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        client = make_client(database_url)
        try:
            application.state.database = await run_in_threadpool(conn, client, database_name)
            yield
        finally:
            await run_in_threadpool(client.close)

    application = FastAPI(
        title="Планировщик событий — MongoDB", version="3.0.0", lifespan=lifespan,
    )
    application.include_router(user_router, prefix="/user")
    application.include_router(event_router, prefix="/event")
    application.add_api_route("/", index, include_in_schema=False)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("planner.main:app", host="0.0.0.0", port=8080, reload=True)
