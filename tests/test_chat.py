"""API and WebSocket regression tests."""

from fastapi.testclient import TestClient

from app.api.endpoints import chat as chat_endpoint
from main import app


client = TestClient(app)


def test_root_describes_available_endpoints() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "EZTalk Chat API",
        "status": "running",
        "health": "/health",
        "docs": "/docs",
        "websocket": "/ws/chat/{session_id}",
    }


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_websocket_streams_chunks_and_preserves_history(monkeypatch, capsys) -> None:
    session_id = "test-session"
    calls: list[list[dict[str, str]]] = []

    async def fake_stream(messages: list):
        calls.append([message.copy() for message in messages])
        chunks = ("Hey! ", "I'm doing well. ", "How about you?")
        for chunk in chunks:
            yield chunk

    monkeypatch.setattr(chat_endpoint, "generate_chat_response", fake_stream)

    with client.websocket_connect(f"/ws/chat/{session_id}") as websocket:
        websocket.send_text("Hello")
        assert websocket.receive_text() == "Hey! "
        assert websocket.receive_text() == "I'm doing well. "
        assert websocket.receive_text() == "How about you?"
        assert websocket.receive_text() == "[DONE]"

        websocket.send_text("Tôi muốn luyện nói tiếng Anh")
        assert websocket.receive_text() == "Hey! "
        assert websocket.receive_text() == "I'm doing well. "
        assert websocket.receive_text() == "How about you?"
        assert websocket.receive_text() == "[DONE]"

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
    assert f"Session connected: {session_id}" in console_output
    assert "message=Hello" in console_output
    assert f"Session disconnected: {session_id}" in console_output
