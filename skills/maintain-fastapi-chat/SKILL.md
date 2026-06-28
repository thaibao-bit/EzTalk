---
name: maintain-fastapi-chat
description: Build, extend, and debug the EZTalk FastAPI backend, especially async WebSocket chat endpoints, LLM HTTP integrations, dependency upgrades, and recurring backend defects. Use for changes under main.py, app/api/endpoints, app/services, requirements.txt, or when a FastAPI/WebSocket bug is reported or observed.
---

# Maintain FastAPI Chat

## Workflow

1. Inspect the current code and `references/bug-patterns.md` before changing behavior.
2. Keep transport logic in `app/api/endpoints`, provider calls in `app/services`, and application wiring in `main.py`.
3. Preserve async boundaries: await socket and HTTP I/O, avoid blocking work in the event loop, and handle disconnects explicitly.
4. Keep public errors safe while retaining enough server-side context for debugging.
5. Validate imports and syntax. Exercise connect/message/disconnect behavior when changing WebSockets.

## WebSocket guardrails

- Accept each connection exactly once before receiving data.
- Receive inside a loop and catch `WebSocketDisconnect` outside that loop.
- Never send after a disconnect.
- Treat `session_id` as an identifier, not proof of authentication.
- Add timeouts, message-size limits, authentication, and rate limits before production exposure.

## LLM integration guardrails

- Keep credentials in environment variables and never log them.
- Use `httpx.AsyncClient`, explicit timeouts, and narrow exception translation.
- Validate provider responses before returning them to the endpoint.
- Prefer one application-scoped client when connection volume becomes significant.

## Recurring-bug protocol

Use `references/bug-patterns.md` as the defect ledger.

- Record only reproduced or evidence-backed defects.
- Increment a pattern only when symptom family and root cause match an existing entry.
- When the count becomes greater than two, create a focused skill at `skills/<bug-pattern-name>/SKILL.md` in the same change. Encode the proven diagnosis, safe fix, regression check, and triggering symptoms. Validate the new skill with the repository's skill validator when available.
- Link the new skill in the ledger and use it for later occurrences.
- Do not merge unrelated failures merely to reach the threshold.

## Verification

- Use `$test-fastapi-chat` for the repository's regression workflow.
- Run `python -m compileall main.py app` after Python changes.
- Start the server and connect a real WebSocket client for behavioral changes when dependencies are available.
- Confirm one acknowledgement per incoming message and a clean disconnect without a server error.
