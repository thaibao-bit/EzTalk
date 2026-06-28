"""ASGI application entrypoint for production imports."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.endpoints.chat import router as chat_router
from app.api.endpoints.evaluation import router as evaluation_router
from app.api.endpoints.sessions import router as sessions_router
from app.core.broadcast import connect_broadcast, disconnect_broadcast
from app.core.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared infrastructure for each API worker process."""

    if settings.run_db_init_on_startup:
        await init_db()
    await connect_broadcast()
    try:
        yield
    finally:
        await disconnect_broadcast()


app = FastAPI(
    title="EZTalk Chat API",
    description="Backend API for English-Vietnamese conversation practice.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(evaluation_router)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Describe the running service for users opening it in a browser."""

    return {
        "name": "EZTalk Chat API",
        "status": "running",
        "health": "/health",
        "docs": "/docs",
        "websocket": "/ws/chat/{session_id}",
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Lightweight health endpoint for containers and load balancers."""

    return {"status": "ok"}
