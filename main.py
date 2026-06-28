"""Application entrypoint for the EZTalk chat API."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.endpoints.chat import router as chat_router
from app.api.endpoints.evaluation import router as evaluation_router
from app.api.endpoints.sessions import router as sessions_router
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize infrastructure required by the API process."""

    await init_db()
    yield


app = FastAPI(
    title="EZTalk Chat API",
    description="Backend API for English-Vietnamese conversation practice.",
    version="0.1.0",
    lifespan=lifespan,
)

# Keeping endpoints in routers makes it easy to add more API modules later.
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


if __name__ == "__main__":
    import os

    import uvicorn

    # Keep port 8000 free for a local vLLM server during development.
    api_port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=api_port, reload=True)
