"""WebSocket endpoint for real-time, streaming AI chat sessions."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.models import MessageRole
from app.db.session import AsyncSessionLocal
from app.repositories.message_repository import (
    create_message,
    list_recent_messages,
    to_llm_messages,
)
from app.services.llm_service import VLLMServiceError, generate_chat_response


router = APIRouter(tags=["chat"])

EVENT_CONNECTED = "connected"
EVENT_ASSISTANT_DELTA = "assistant_delta"
EVENT_ASSISTANT_DONE = "assistant_done"
EVENT_ERROR = "error"


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str) -> None:
    """Stream one vLLM response per incoming user message as JSON events.

    Protocol:
    - ``connected``: emitted once after the socket is accepted.
    - ``assistant_delta``: one event per model text chunk.
    - ``assistant_done``: response boundary marker for the client.
    - ``error``: recoverable validation/upstream error.
    """

    settings = get_settings()
    user_id = websocket.query_params.get("user_id") or "guest"
    await websocket.accept()
    await websocket.send_json(
        {
            "type": EVENT_CONNECTED,
            "session_id": session_id,
            "user_id": user_id,
            "message": "WebSocket connected.",
        }
    )
    print(
        f"[WebSocket] Session connected: session_id={session_id} user_id={user_id}",
        flush=True,
    )

    try:
        while True:
            user_message = (await websocket.receive_text()).strip()
            print(
                f"[WebSocket] session_id={session_id} user_id={user_id} "
                f"message={user_message}",
                flush=True,
            )

            if not user_message:
                await _send_error(
                    websocket,
                    session_id=session_id,
                    message="Vui lòng gửi một tin nhắn có nội dung.",
                    code="empty_message",
                )
                continue

            async with AsyncSessionLocal() as db_session:
                persisted_history = await list_recent_messages(
                    db_session,
                    session_id=session_id,
                    user_id=user_id,
                    limit=settings.websocket_max_history_messages,
                )

            conversation = [
                *to_llm_messages(persisted_history),
                {"role": MessageRole.USER.value, "content": user_message},
            ]
            response_chunks: list[str] = []

            try:
                # Each upstream SSE delta is forwarded immediately; we never
                # buffer the full model answer before sending it to the client.
                async for chunk in generate_chat_response(conversation):
                    response_chunks.append(chunk)
                    await websocket.send_json(
                        {
                            "type": EVENT_ASSISTANT_DELTA,
                            "session_id": session_id,
                            "delta": chunk,
                        }
                    )
            except VLLMServiceError as exc:
                print(
                    f"[vLLM] session_id={session_id} error={exc}",
                    flush=True,
                )
                await _send_error(
                    websocket,
                    session_id=session_id,
                    message=(
                        "AI server hiện chưa phản hồi. "
                        "Bạn vui lòng thử lại sau nhé."
                    ),
                    code="llm_unavailable",
                )
            else:
                full_response = "".join(response_chunks)

                try:
                    async with AsyncSessionLocal() as db_session:
                        # Persist only successful turns. If the upstream model
                        # fails, the current user message is not stored as
                        # dangling context for the next retry.
                        await create_message(
                            db_session,
                            session_id=session_id,
                            user_id=user_id,
                            role=MessageRole.USER,
                            content=user_message,
                        )
                        await create_message(
                            db_session,
                            session_id=session_id,
                            user_id=user_id,
                            role=MessageRole.ASSISTANT,
                            content=full_response,
                        )
                except SQLAlchemyError as exc:
                    print(
                        f"[DB] session_id={session_id} user_id={user_id} "
                        f"error={exc}",
                        flush=True,
                    )
                    await _send_error(
                        websocket,
                        session_id=session_id,
                        message=(
                            "Có lỗi hệ thống xảy ra, "
                            "cuộc hội thoại tạm thời chưa được lưu."
                        ),
                        code="database_error",
                    )
                    continue

                await websocket.send_json(
                    {
                        "type": EVENT_ASSISTANT_DONE,
                        "session_id": session_id,
                        "message": full_response,
                    }
                )
    except WebSocketDisconnect:
        print(f"[WebSocket] Session disconnected: {session_id}", flush=True)


async def _send_error(
    websocket: WebSocket,
    *,
    session_id: str,
    message: str,
    code: str,
) -> None:
    """Send a recoverable WebSocket error without closing the connection."""

    await websocket.send_json(
        {
            "type": EVENT_ERROR,
            "session_id": session_id,
            "code": code,
            "message": message,
        }
    )
