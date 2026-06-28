"""HTTP endpoint for AI conversation evaluation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.auth_repository import get_user_by_api_key
from app.services.evaluation_service import (
    EvaluationServiceError,
    evaluate_session,
)


router = APIRouter(prefix="/api/v1/sessions", tags=["evaluation"])


@router.post("/{session_id}/evaluate")
async def evaluate_chat_session(
    session_id: str,
    api_key: str,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Evaluate one persisted conversation session with the configured LLM."""

    user = await get_user_by_api_key(db_session, api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    try:
        return await evaluate_session(session_id=session_id, user_id=user.id)
    except EvaluationServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI evaluation service is temporarily unavailable.",
        ) from exc
