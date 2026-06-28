"""AI-powered conversation evaluation service."""

from typing import Any
import json

import httpx

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories.message_repository import list_session_messages


EVALUATION_SYSTEM_PROMPT = """
You are a senior language coach and emotional-intelligence evaluator for an
English-Vietnamese speaking practice app.

Your job:
- Analyze the full conversation transcript.
- Evaluate only the user's language and conversation behavior.
- Be practical, kind, specific, and useful for a Vietnamese learner.
- Detect grammar, vocabulary range, naturalness, confidence, and EQ/social flow.
- Do not invent messages that are not in the transcript.

Return ONLY one valid JSON object. Do not wrap it in Markdown. Do not add any
extra commentary outside JSON.

Required JSON schema:
{
  "grammar_score": int from 0 to 100,
  "vocabulary_score": int from 0 to 100,
  "eq_score": int from 0 to 100,
  "cefr_level": "A1" | "A2" | "B1" | "B2" | "C1" | "C2",
  "grammar_errors": [
    {
      "original": string,
      "corrected": string,
      "explanation_vi": string
    }
  ],
  "suggested_replies": [string],
  "overall_feedback_vi": string
}
""".strip()


class EvaluationServiceError(RuntimeError):
    """Raised when the LLM cannot produce a valid evaluation."""


async def evaluate_session(session_id: str, user_id: str) -> dict:
    """Evaluate a persisted chat session and return structured feedback."""

    async with AsyncSessionLocal() as db_session:
        messages = await list_session_messages(
            db_session,
            session_id=session_id,
            user_id=user_id or "guest",
        )

    transcript = _format_transcript(messages)
    payload: dict[str, Any] = {
        "model": settings.vllm_model,
        "messages": [
            {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Evaluate this conversation transcript.\n\n"
                    f"session_id: {session_id}\n"
                    f"user_id: {user_id or 'guest'}\n\n"
                    f"{transcript}"
                ),
            },
        ],
        "stream": False,
        "temperature": 0.2,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
    }
    headers = {"Accept": "application/json"}
    if settings.vllm_api_key:
        headers["Authorization"] = f"Bearer {settings.vllm_api_key}"

    endpoint = f"{settings.vllm_base_url.rstrip('/')}/chat/completions"

    try:
        async with _create_http_client() as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            completion = response.json()
            content = completion["choices"][0]["message"]["content"]
            return json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise EvaluationServiceError("vLLM returned an invalid evaluation") from exc


def _format_transcript(messages: list) -> str:
    """Render DB messages into a compact transcript for evaluation."""

    if not messages:
        return "Transcript is empty."

    return "\n".join(
        f"{message.role.value}: {message.content}" for message in messages
    )


def _create_http_client() -> httpx.AsyncClient:
    """Create the HTTP client used for evaluation calls.

    Kept as a small factory so tests can monkeypatch it with ``MockTransport``
    without touching global network behavior.
    """

    timeout = httpx.Timeout(
        connect=10.0,
        read=settings.vllm_timeout_seconds,
        write=30.0,
        pool=10.0,
    )
    return httpx.AsyncClient(timeout=timeout)
