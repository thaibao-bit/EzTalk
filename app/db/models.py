"""SQLAlchemy ORM models for EZTalk."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class MessageRole(StrEnum):
    """Allowed chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    """Persisted chat message for one conversation session."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(128),
        index=True,
        nullable=False,
        default="guest",
        server_default="guest",
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
