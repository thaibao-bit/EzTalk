"""WebSocket endpoint for real-time, streaming AI chat sessions."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.llm_service import VLLMServiceError, generate_chat_response


router = APIRouter(tags=["chat"])

STREAM_DONE_MARKER = "[DONE]"
MAX_HISTORY_MESSAGES = 40


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str) -> None:
    """Stream one vLLM response per incoming user message.

    Every model delta is sent as an individual WebSocket text frame. A final
    ``[DONE]`` frame marks the response boundary for the client.
    """

    await websocket.accept()
    print(f"[WebSocket] Session connected: {session_id}", flush=True)
    conversation: list[dict[str, str]] = []

    try:
        while True:
            user_message = (await websocket.receive_text()).strip()
            print(
                f"[WebSocket] session_id={session_id} message={user_message}",
                flush=True,
            )

            if not user_message:
                await websocket.send_text("Vui lòng gửi một tin nhắn có nội dung.")
                await websocket.send_text(STREAM_DONE_MARKER)
                continue

            conversation.append({"role": "user", "content": user_message})
            response_chunks: list[str] = []

            try:
                # Each upstream SSE delta is forwarded immediately; we never
                # buffer the full model answer before sending it to the client.
                async for chunk in generate_chat_response(conversation):
                    response_chunks.append(chunk)
                    await websocket.send_text(chunk)
            except VLLMServiceError as exc:
                # Remove the failed user turn so retrying does not corrupt the
                # conversation history. Keep internal details in server logs.
                conversation.pop()
                print(
                    f"[vLLM] session_id={session_id} error={exc}",
                    flush=True,
                )
                await websocket.send_text(
                    "AI server hiện chưa phản hồi. Bạn vui lòng thử lại sau nhé."
                )
            else:
                conversation.append(
                    {"role": "assistant", "content": "".join(response_chunks)}
                )
                # Bound in-memory history for long-lived mobile/web connections.
                conversation = conversation[-MAX_HISTORY_MESSAGES:]

            await websocket.send_text(STREAM_DONE_MARKER)
    except WebSocketDisconnect:
        print(f"[WebSocket] Session disconnected: {session_id}", flush=True)
