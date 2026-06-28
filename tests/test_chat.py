"""API and WebSocket regression tests."""

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.endpoints import chat as chat_endpoint
from app.db.session import AsyncSessionLocal
from app.repositories.auth_repository import create_user
from main import app


@pytest.fixture
def client() -> TestClient:
    """Run the FastAPI lifespan for each test client."""

    with TestClient(app) as test_client:
        yield test_client


async def _seed_user(user_id: str, api_key: str) -> None:
    async with AsyncSessionLocal() as db_session:
        async with db_session.begin():
            await create_user(db_session, user_id=user_id, api_key=api_key)


def test_root_describes_available_endpoints(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "EZTalk Chat API",
        "status": "running",
        "health": "/health",
        "docs": "/docs",
        "websocket": "/ws/chat/{session_id}",
    }


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_websocket_streams_chunks_and_preserves_history(
    client: TestClient,
    monkeypatch,
    capsys,
) -> None:
    session_id = f"test-session-{uuid4()}"
    user_id = f"user-{uuid4()}"
    api_key = f"key-{uuid4()}"
    calls: list[list[dict[str, str]]] = []

    async def fake_stream(messages: list):
        calls.append([message.copy() for message in messages])
        chunks = ("Hey! ", "I'm doing well. ", "How about you?")
        for chunk in chunks:
            yield chunk

    monkeypatch.setattr(chat_endpoint, "generate_chat_response", fake_stream)
    asyncio.run(_seed_user(user_id, api_key))

    with client.websocket_connect(
        f"/ws/chat/{session_id}?api_key={api_key}"
    ) as websocket:
        assert websocket.receive_json() == {
            "type": "connected",
            "session_id": session_id,
            "user_id": user_id,
            "message": "WebSocket connected.",
        }

        websocket.send_text("Hello")
        assert websocket.receive_json() == {
            "type": "assistant_delta",
            "session_id": session_id,
            "delta": "Hey! ",
        }
        assert websocket.receive_json() == {
            "type": "assistant_delta",
            "session_id": session_id,
            "delta": "I'm doing well. ",
        }
        assert websocket.receive_json() == {
            "type": "assistant_delta",
            "session_id": session_id,
            "delta": "How about you?",
        }
        assert websocket.receive_json() == {
            "type": "assistant_done",
            "session_id": session_id,
            "message": "Hey! I'm doing well. How about you?",
        }

        websocket.send_text("Tôi muốn luyện nói tiếng Anh")
        assert websocket.receive_json() == {
            "type": "assistant_delta",
            "session_id": session_id,
            "delta": "Hey! ",
        }
        assert websocket.receive_json() == {
            "type": "assistant_delta",
            "session_id": session_id,
            "delta": "I'm doing well. ",
        }
        assert websocket.receive_json() == {
            "type": "assistant_delta",
            "session_id": session_id,
            "delta": "How about you?",
        }
        assert websocket.receive_json() == {
            "type": "assistant_done",
            "session_id": session_id,
            "message": "Hey! I'm doing well. How about you?",
        }

    assert calls[0] == [{"role": "user", "content": "Hello"}]
    assert calls[1] == [
        {"role": "user", "content": "Hello"},
        {
            "role": "assistant",
            "content": "Hey! I'm doing well. How about you?",
        },
        {"role": "user", "content": "Tôi muốn luyện nói tiếng Anh"},
    ]

    console_output = capsys.readouterr().out
    assert f"session_id={session_id} user_id={user_id}" in console_output
    assert "message=Hello" in console_output
    assert f"Session disconnected: {session_id}" in console_output

    response = client.get(
        f"/api/v1/sessions/{session_id}/messages",
        params={"api_key": api_key},
    )

    assert response.status_code == 200
    persisted_messages = response.json()
    assert [
        {
            "session_id": message["session_id"],
            "user_id": message["user_id"],
            "role": message["role"],
            "content": message["content"],
        }
        for message in persisted_messages
    ] == [
        {
            "session_id": session_id,
            "user_id": user_id,
            "role": "user",
            "content": "Hello",
        },
        {
            "session_id": session_id,
            "user_id": user_id,
            "role": "assistant",
            "content": "Hey! I'm doing well. How about you?",
        },
        {
            "session_id": session_id,
            "user_id": user_id,
            "role": "user",
            "content": "Tôi muốn luyện nói tiếng Anh",
        },
        {
            "session_id": session_id,
            "user_id": user_id,
            "role": "assistant",
            "content": "Hey! I'm doing well. How about you?",
        },
    ]
    assert all(isinstance(message["id"], int) for message in persisted_messages)
    assert all("created_at" in message for message in persisted_messages)


def test_websocket_returns_error_event_for_empty_message(client: TestClient) -> None:
    session_id = f"empty-message-session-{uuid4()}"
    user_id = f"empty-message-user-{uuid4()}"
    api_key = f"key-{uuid4()}"

    asyncio.run(_seed_user(user_id, api_key))

    with client.websocket_connect(
        f"/ws/chat/{session_id}?api_key={api_key}"
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"

        websocket.send_text("   ")

        assert websocket.receive_json() == {
            "type": "error",
            "session_id": session_id,
            "code": "empty_message",
            "message": "Vui lòng gửi một tin nhắn có nội dung.",
        }


def test_websocket_returns_auth_error_for_invalid_api_key(
    client: TestClient,
) -> None:
    session_id = f"auth-error-session-{uuid4()}"

    with client.websocket_connect(
        f"/ws/chat/{session_id}?api_key=invalid"
    ) as websocket:
        assert websocket.receive_json() == {
            "type": "error",
            "session_id": session_id,
            "code": "auth_error",
            "message": "API key không hợp lệ hoặc đã hết hạn.",
        }


def test_get_session_messages_returns_empty_list_for_unknown_session(
    client: TestClient,
) -> None:
    session_id = f"unknown-session-{uuid4()}"
    user_id = f"unknown-session-user-{uuid4()}"
    api_key = f"key-{uuid4()}"

    asyncio.run(_seed_user(user_id, api_key))

    response = client.get(
        f"/api/v1/sessions/{session_id}/messages",
        params={"api_key": api_key},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_get_session_messages_rejects_invalid_api_key(client: TestClient) -> None:
    session_id = f"invalid-key-session-{uuid4()}"

    response = client.get(
        f"/api/v1/sessions/{session_id}/messages",
        params={"api_key": "invalid"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key."}


def test_session_messages_are_filtered_by_user_id(
    client: TestClient,
    monkeypatch,
) -> None:
    session_id = f"shared-session-{uuid4()}"
    first_user_id = f"first-user-{uuid4()}"
    second_user_id = f"second-user-{uuid4()}"
    first_api_key = f"key-{uuid4()}"
    second_api_key = f"key-{uuid4()}"

    async def fake_stream(messages: list):
        yield f"Reply to {messages[-1]['content']}"

    monkeypatch.setattr(chat_endpoint, "generate_chat_response", fake_stream)
    asyncio.run(_seed_user(first_user_id, first_api_key))
    asyncio.run(_seed_user(second_user_id, second_api_key))

    with client.websocket_connect(
        f"/ws/chat/{session_id}-first?api_key={first_api_key}"
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_text("Hello from first user")
        assert websocket.receive_json()["type"] == "assistant_delta"
        assert websocket.receive_json()["type"] == "assistant_done"

    with client.websocket_connect(
        f"/ws/chat/{session_id}-second?api_key={second_api_key}"
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_text("Hello from second user")
        assert websocket.receive_json()["type"] == "assistant_delta"
        assert websocket.receive_json()["type"] == "assistant_done"

    first_response = client.get(
        f"/api/v1/sessions/{session_id}-first/messages",
        params={"api_key": first_api_key},
    )
    second_response = client.get(
        f"/api/v1/sessions/{session_id}-second/messages",
        params={"api_key": second_api_key},
    )

    assert [message["content"] for message in first_response.json()] == [
        "Hello from first user",
        "Reply to Hello from first user",
    ]
    assert [message["content"] for message in second_response.json()] == [
        "Hello from second user",
        "Reply to Hello from second user",
    ]


def test_websocket_returns_database_error_event_when_persistence_fails(
    client: TestClient,
    monkeypatch,
) -> None:
    session_id = f"db-error-session-{uuid4()}"
    user_id = f"db-error-user-{uuid4()}"
    api_key = f"key-{uuid4()}"

    async def fake_stream(_messages: list):
        yield "This response cannot be saved."

    async def fail_create_message(*_args, **_kwargs):
        raise SQLAlchemyError("database is unavailable")

    monkeypatch.setattr(chat_endpoint, "generate_chat_response", fake_stream)
    monkeypatch.setattr(chat_endpoint, "create_conversation_turn", fail_create_message)
    asyncio.run(_seed_user(user_id, api_key))

    with client.websocket_connect(
        f"/ws/chat/{session_id}?api_key={api_key}"
    ) as websocket:
        assert websocket.receive_json() == {
            "type": "connected",
            "session_id": session_id,
            "user_id": user_id,
            "message": "WebSocket connected.",
        }

        websocket.send_text("Please save this")

        assert websocket.receive_json() == {
            "type": "assistant_delta",
            "session_id": session_id,
            "delta": "This response cannot be saved.",
        }
        assert websocket.receive_json() == {
            "type": "error",
            "session_id": session_id,
            "code": "database_error",
            "message": (
                "Có lỗi hệ thống xảy ra, "
                "cuộc hội thoại tạm thời chưa được lưu."
            ),
        }
