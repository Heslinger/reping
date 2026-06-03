import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, payments, payloads, pingbacks, websocket
from app.core.config import get_settings
from app.core.redis import close_redis
from app.db.models import Base
from app.db.session import engine
from app.listeners.dns import start_dns_listener
from app.services.cleanup import cleanup_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(cleanup_loop(stop_event))
    dns_transport = None
    if settings.dns_listen_port:
        dns_transport = await start_dns_listener()

    try:
        yield
    finally:
        stop_event.set()
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        if dns_transport is not None:
            dns_transport.close()
        await close_redis()
        await engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(settings.frontend_url).rstrip("/")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
api.include_router(auth.router)
api.include_router(payloads.router)
api.include_router(pingbacks.router)
api.include_router(payments.router)

app.mount("/api", api)
app.include_router(websocket.router)
app.include_router(pingbacks.capture_router)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
