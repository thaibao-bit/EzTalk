"""Persistence helpers for chat messages."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageRole


async def create_message(
    session: AsyncSession,
    *,
    session_id: str,
    user_id: str,
    role: MessageRole,
    content: str,
) -> Message:
    """Insert and commit one chat message."""

    message = Message(
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def list_recent_messages(
    session: AsyncSession,
    *,
    session_id: str,
    user_id: str,
    limit: int,
) -> list[Message]:
    """Return recent messages in chronological order for LLM context."""

    statement = (
        select(Message)
        .where(Message.session_id == session_id, Message.user_id == user_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    result = await session.execute(statement)
    messages = list(result.scalars().all())
    return list(reversed(messages))


async def list_session_messages(
    session: AsyncSession,
    *,
    session_id: str,
    user_id: str,
) -> list[Message]:
    """Return all messages for a session in chronological order."""

    statement = (
        select(Message)
        .where(Message.session_id == session_id, Message.user_id == user_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


def to_llm_messages(messages: list[Message]) -> list[dict[str, str]]:
    """Convert ORM messages into OpenAI-compatible chat history."""

    return [
        {
            "role": message.role.value,
            "content": message.content,
        }
        for message in messages
    ]
