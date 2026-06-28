"""HTTP endpoint for AI conversation evaluation."""

from fastapi import APIRouter, HTTPException

from app.services.evaluation_service import (
    EvaluationServiceError,
    evaluate_session,
)


router = APIRouter(prefix="/api/v1/sessions", tags=["evaluation"])


@router.post("/{session_id}/evaluate")
async def evaluate_chat_session(
    session_id: str,
    user_id: str = "guest",
) -> dict:
    """Evaluate one persisted conversation session with the configured LLM."""

    try:
        return await evaluate_session(session_id=session_id, user_id=user_id or "guest")
    except EvaluationServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI evaluation service is temporarily unavailable.",
        ) from exc
