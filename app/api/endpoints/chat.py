"""WebSocket endpoint for real-time, streaming AI chat sessions."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.exc import SQLAlchemyError

from app.core.broadcast import publish_session_event, subscribe_session_events
from app.core.config import get_settings
from app.db.models import MessageRole
from app.db.session import AsyncSessionLocal
from app.repositories.auth_repository import get_user_by_api_key
from app.repositories.message_repository import (
    create_conversation_turn,
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
    api_key = websocket.query_params.get("api_key") or ""
    await websocket.accept()

    async with AsyncSessionLocal() as db_session:
        user = await get_user_by_api_key(db_session, api_key)

    if user is None:
        await _send_error(
            websocket,
            session_id=session_id,
            message="API key không hợp lệ hoặc đã hết hạn.",
            code="auth_error",
        )
        await websocket.close(code=1008)
        return

    user_id = user.id
    subscription_task: asyncio.Task | None = None
    if settings.redis_broadcast_enabled:
        subscription_task = asyncio.create_task(
            _forward_session_events(websocket, session_id)
        )

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
                    use_broadcast=settings.redis_broadcast_enabled,
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
                    delta_event = {
                            "type": EVENT_ASSISTANT_DELTA,
                            "session_id": session_id,
                            "delta": chunk,
                        }
                    await _emit_session_event(
                        websocket,
                        session_id=session_id,
                        event=delta_event,
                        use_broadcast=settings.redis_broadcast_enabled,
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
                    use_broadcast=settings.redis_broadcast_enabled,
                )
            else:
                full_response = "".join(response_chunks)

                try:
                    async with AsyncSessionLocal() as db_session:
                        async with db_session.begin():
                            # Persist the user/assistant pair atomically. If
                            # either insert fails, neither message is committed.
                            await create_conversation_turn(
                                db_session,
                                session_id=session_id,
                                user_id=user_id,
                                user_content=user_message,
                                assistant_content=full_response,
                            )
                except PermissionError as exc:
                    print(
                        f"[Auth] session_id={session_id} user_id={user_id} "
                        f"error={exc}",
                        flush=True,
                    )
                    await _send_error(
                        websocket,
                        session_id=session_id,
                        message="Bạn không có quyền truy cập session này.",
                        code="auth_error",
                        use_broadcast=settings.redis_broadcast_enabled,
                    )
                    continue
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
                        use_broadcast=settings.redis_broadcast_enabled,
                    )
                    continue

                done_event = {
                        "type": EVENT_ASSISTANT_DONE,
                        "session_id": session_id,
                        "message": full_response,
                    }
                await _emit_session_event(
                    websocket,
                    session_id=session_id,
                    event=done_event,
                    use_broadcast=settings.redis_broadcast_enabled,
                )
    except WebSocketDisconnect:
        print(f"[WebSocket] Session disconnected: {session_id}", flush=True)
    finally:
        if subscription_task is not None:
            subscription_task.cancel()


async def _send_error(
    websocket: WebSocket,
    *,
    session_id: str,
    message: str,
    code: str,
    use_broadcast: bool = False,
) -> None:
    """Send a recoverable WebSocket error without closing the connection."""

    error_event = {
            "type": EVENT_ERROR,
            "session_id": session_id,
            "code": code,
            "message": message,
        }
    await _emit_session_event(
        websocket,
        session_id=session_id,
        event=error_event,
        use_broadcast=use_broadcast,
    )


async def _emit_session_event(
    websocket: WebSocket,
    *,
    session_id: str,
    event: dict,
    use_broadcast: bool,
) -> None:
    """Send locally in dev, or fan out through Redis in production."""

    if use_broadcast:
        await publish_session_event(session_id, event)
    else:
        await websocket.send_json(event)


async def _forward_session_events(websocket: WebSocket, session_id: str) -> None:
    """Forward Redis Pub/Sub session events to this WebSocket connection."""

    async for event in subscribe_session_events(session_id):
        await websocket.send_json(event)
