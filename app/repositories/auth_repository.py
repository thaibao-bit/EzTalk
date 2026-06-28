"""Authentication repository helpers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_user_by_api_key(session: AsyncSession, api_key: str) -> User | None:
    """Return the user matching an API key, if any."""

    result = await session.execute(select(User).where(User.api_key == api_key))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    user_id: str,
    api_key: str,
) -> User:
    """Create a user for tests, seeds, and local bootstrap scripts."""

    user = User(id=user_id, api_key=api_key)
    session.add(user)
    await session.flush()
    return user
