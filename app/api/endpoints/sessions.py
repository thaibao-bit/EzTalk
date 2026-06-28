"""HTTP endpoints for reading chat session history."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MessageRole
from app.db.session import get_db_session
from app.repositories.message_repository import list_session_messages


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


class MessageResponse(BaseModel):
    """Serialized chat message returned to web/mobile clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    user_id: str
    role: MessageRole
    content: str
    created_at: datetime


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: str,
    user_id: str = "guest",
    db_session: AsyncSession = Depends(get_db_session),
) -> list[MessageResponse]:
    """Return all persisted messages for one chat session.

    Messages are sorted chronologically so clients can render the transcript
    directly without doing additional ordering work.
    """

    messages = await list_session_messages(
        db_session,
        session_id=session_id,
        user_id=user_id or "guest",
    )
    return [MessageResponse.model_validate(message) for message in messages]
