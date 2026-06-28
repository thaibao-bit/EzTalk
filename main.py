"""Development entrypoint wrapper.

Production imports use ``app.main:app``. This module remains for local commands
and backwards compatibility with existing tests/scripts.
"""

from app.main import app


__all__ = ["app"]


if __name__ == "__main__":
    import os

    import uvicorn

    # Keep port 8000 free for a local vLLM server during development.
    api_port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=api_port, reload=True)
