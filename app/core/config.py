"""Application settings loaded from environment variables.

The project intentionally keeps this layer lightweight for now: no extra
settings dependency is required, but every runtime value still has one clear
source of truth.
"""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the FastAPI chat backend."""

    app_name: str = "EZTalk Chat API"
    app_version: str = "0.1.0"
    api_port: int = 8080
    websocket_max_history_messages: int = 40
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model: str = "default"
    vllm_api_key: str | None = None
    vllm_timeout_seconds: float = 120.0
    database_url: str = "sqlite+aiosqlite:///./data/eztalk.db"
    redis_url: str = "redis://localhost:6379/0"
    redis_broadcast_enabled: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    run_db_init_on_startup: bool = True


def get_settings() -> Settings:
    """Create settings from environment variables.

    This function is intentionally simple and side-effect free, so tests can
    override environment variables with ``monkeypatch`` and instantiate fresh
    settings when needed.
    """

    return Settings(
        api_port=_get_int("API_PORT", 8080),
        websocket_max_history_messages=_get_int("WEBSOCKET_MAX_HISTORY_MESSAGES", 40),
        vllm_base_url=(
            os.getenv("VLLM_BASE_URL")
            or os.getenv("LLM_API_URL")
            or "http://localhost:8000/v1"
        ),
        vllm_model=os.getenv("VLLM_MODEL") or os.getenv("LLM_MODEL") or "default",
        vllm_api_key=os.getenv("VLLM_API_KEY") or os.getenv("LLM_API_KEY"),
        vllm_timeout_seconds=_get_float("VLLM_TIMEOUT_SECONDS", 120.0),
        database_url=os.getenv("DATABASE_URL")
        or "sqlite+aiosqlite:///./data/eztalk.db",
        redis_url=os.getenv("REDIS_URL") or "redis://localhost:6379/0",
        redis_broadcast_enabled=_get_bool("ENABLE_REDIS_BROADCAST", False),
        db_pool_size=_get_int("DB_POOL_SIZE", 5),
        db_max_overflow=_get_int("DB_MAX_OVERFLOW", 10),
        run_db_init_on_startup=_get_bool("RUN_DB_INIT_ON_STARTUP", True),
    )


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


settings = get_settings()
