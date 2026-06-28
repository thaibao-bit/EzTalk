"""Application entrypoint for the EZTalk chat API."""

from fastapi import FastAPI

from app.api.endpoints.chat import router as chat_router


app = FastAPI(
    title="EZTalk Chat API",
    description="Backend API for English-Vietnamese conversation practice.",
    version="0.1.0",
)

# Keeping endpoints in routers makes it easy to add more API modules later.
app.include_router(chat_router)


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
