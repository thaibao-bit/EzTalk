"""Environment-aware application settings."""

from functools import lru_cache
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> str:
    """Return the dotenv file for the active environment."""

    app_env = os.getenv("APP_ENV", "development").lower()
    return f".env.{app_env}"


class Settings(BaseSettings):
    """Runtime settings loaded from system env and environment-specific files."""

    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: str = "development"
    PROJECT_NAME: str = "EZTalk - AI English Coach (Dev)"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/eztalk.db"
    RUN_DB_INIT_ON_STARTUP: bool = True

    ENABLE_REDIS_BROADCAST: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"

    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    VLLM_MODEL: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"

    API_PORT: int = 8080
    APP_VERSION: str = "0.1.0"
    WEBSOCKET_MAX_HISTORY_MESSAGES: int = 40
    VLLM_API_KEY: str | None = None
    LLM_API_KEY: str | None = None
    VLLM_TIMEOUT_SECONDS: float = 120.0
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    POSTGRES_PASSWORD: str | None = Field(default=None, exclude=True)

    @property
    def app_name(self) -> str:
        return self.PROJECT_NAME

    @property
    def app_version(self) -> str:
        return self.APP_VERSION

    @property
    def api_port(self) -> int:
        return self.API_PORT

    @property
    def websocket_max_history_messages(self) -> int:
        return self.WEBSOCKET_MAX_HISTORY_MESSAGES

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def run_db_init_on_startup(self) -> bool:
        return self.RUN_DB_INIT_ON_STARTUP

    @property
    def redis_broadcast_enabled(self) -> bool:
        return self.ENABLE_REDIS_BROADCAST

    @property
    def redis_url(self) -> str:
        return self.REDIS_URL

    @property
    def vllm_base_url(self) -> str:
        return self.VLLM_BASE_URL

    @property
    def vllm_model(self) -> str:
        return self.VLLM_MODEL

    @property
    def vllm_api_key(self) -> str | None:
        return self.VLLM_API_KEY or self.LLM_API_KEY

    @property
    def vllm_timeout_seconds(self) -> float:
        return self.VLLM_TIMEOUT_SECONDS

    @property
    def db_pool_size(self) -> int:
        return self.DB_POOL_SIZE

    @property
    def db_max_overflow(self) -> int:
        return self.DB_MAX_OVERFLOW


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for the active environment."""

    return Settings()


settings = get_settings()
