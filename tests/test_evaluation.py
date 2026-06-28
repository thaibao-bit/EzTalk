"""Regression tests for AI session evaluation."""

import asyncio
import json
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
import pytest

from app.db.models import MessageRole
from app.db.session import AsyncSessionLocal
from app.repositories.auth_repository import create_user
from app.repositories.message_repository import create_message
from app.services import evaluation_service
from main import app


@pytest.fixture
def client() -> TestClient:
    """Run the FastAPI lifespan for each test client."""

    with TestClient(app) as test_client:
        yield test_client


def test_evaluate_session_posts_transcript_to_vllm_and_returns_json(
    client: TestClient,
    monkeypatch,
) -> None:
    session_id = f"evaluation-session-{uuid4()}"
    user_id = f"evaluation-user-{uuid4()}"
    api_key = f"key-{uuid4()}"
    captured_payloads: list[dict] = []

    async def seed_messages() -> None:
        async with AsyncSessionLocal() as db_session:
            async with db_session.begin():
                await create_user(db_session, user_id=user_id, api_key=api_key)
            await create_message(
                db_session,
                session_id=session_id,
                user_id=user_id,
                role=MessageRole.USER,
                content="I go to school yesterday.",
            )
            await create_message(
                db_session,
                session_id=session_id,
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content="Oh nice, what did you do there?",
            )

    asyncio.run(seed_messages())

    evaluation_result = {
        "grammar_score": 72,
        "vocabulary_score": 68,
        "eq_score": 81,
        "cefr_level": "A2",
        "grammar_errors": [
            {
                "original": "I go to school yesterday.",
                "corrected": "I went to school yesterday.",
                "explanation_vi": "Khi nói về hôm qua, cần dùng thì quá khứ.",
            }
        ],
        "suggested_replies": [
            "I went there to meet my classmates.",
            "It was fun, but I felt a little tired.",
        ],
        "overall_feedback_vi": "Bạn giao tiếp rõ ý và nên chú ý thì quá khứ.",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured_payloads.append(payload)

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(evaluation_result),
                        }
                    }
                ]
            },
        )

    def create_mock_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://vllm.example.test",
        )

    monkeypatch.setattr(
        evaluation_service,
        "_create_http_client",
        create_mock_client,
    )

    response = client.post(
        f"/api/v1/sessions/{session_id}/evaluate",
        params={"api_key": api_key},
    )

    assert response.status_code == 200
    assert response.json() == evaluation_result

    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["stream"] is False
    assert payload["messages"][0]["role"] == "system"
    transcript_prompt = payload["messages"][1]["content"]
    assert f"session_id: {session_id}" in transcript_prompt
    assert f"user_id: {user_id}" in transcript_prompt
    assert "user: I go to school yesterday." in transcript_prompt
    assert "assistant: Oh nice, what did you do there?" in transcript_prompt
