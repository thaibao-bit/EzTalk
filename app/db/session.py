"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.db.models import Base


settings = get_settings()

if settings.database_url.startswith("sqlite+aiosqlite:///./"):
    database_path = Path(settings.database_url.removeprefix("sqlite+aiosqlite:///"))
    database_path.parent.mkdir(parents=True, exist_ok=True)

engine_kwargs = {"echo": False, "pool_pre_ping": True}
if not settings.database_url.startswith("sqlite+"):
    engine_kwargs.update(
        {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "connect_args": {"statement_cache_size": 0},
        }
    )

engine = create_async_engine(settings.database_url, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create database tables for local/dev usage.

    A real production deployment should move schema changes to Alembic
    migrations, but automatic table creation is pragmatic for this SQLite
    phase and keeps local onboarding fast.
    """

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_ensure_sqlite_user_id_column)


def _ensure_sqlite_user_id_column(sync_connection) -> None:
    """Backfill the ``messages.user_id`` column for existing SQLite DB files."""

    if sync_connection.dialect.name != "sqlite":
        return

    inspector = inspect(sync_connection)
    table_names = inspector.get_table_names()
    if "messages" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("messages")}
    if "user_id" in columns:
        return

    sync_connection.execute(
        text(
            "ALTER TABLE messages "
            "ADD COLUMN user_id VARCHAR(128) NOT NULL DEFAULT 'guest'"
        )
    )


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield one async database session."""

    async with AsyncSessionLocal() as session:
        yield session
