"""SQLAlchemy ORM models for EZTalk."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class MessageRole(StrEnum):
    """Allowed chat message roles."""

    USER = "user"
    ASSISTANT = "assistant"


class User(Base):
    """Application user authenticated by API key."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    api_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class Session(Base):
    """Conversation session owned by one user."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")


class Message(Base):
    """Persisted chat message for one conversation session."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("sessions.id"),
        index=True,
        nullable=False,
    )
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

    session: Mapped[Session] = relationship(back_populates="messages")
