---
name: test-fastapi-chat
description: Add, run, and maintain regression tests for the EZTalk FastAPI backend, including HTTP health endpoints, WebSocket connect-message-disconnect behavior, asynchronous LLM HTTP calls, error translation, and Docker runtime checks. Use when changing backend behavior, fixing a bug, adding test cases, reviewing test coverage, or verifying a container build.
---

# Test FastAPI Chat

## Test workflow

1. Activate `.venv` or invoke `.venv/Scripts/python.exe` directly on Windows.
2. Install `requirements-dev.txt` when the environment is new or dependency pins change.
3. Add the smallest regression test that fails for the defect or missing behavior.
4. Prefer deterministic in-process tests; never call a real LLM provider from the test suite.
5. Run `python -m pytest -q`, then run syntax compilation.
6. Build the Docker image after runtime dependencies or container files change.

## HTTP and WebSocket tests

- Use FastAPI/Starlette `TestClient` for endpoint-level tests.
- Enter WebSockets with `websocket_connect(...)` so disconnect cleanup always runs.
- Assert one response for each input message.
- Cover connection, repeated messages, Unicode content, and clean disconnect behavior.
- Capture console output only when logging/debug output is part of the requirement.

## LLM service tests

- Inject `httpx.AsyncClient` configured with `httpx.MockTransport`.
- Assert URL, authorization header, payload, and parsed reply.
- Cover missing configuration, non-success HTTP status, malformed JSON shape, and empty replies.
- Use `asyncio.run` for isolated async unit cases unless the suite adopts a dedicated async pytest plugin.
- Never place real keys, conversation data, or production URLs in fixtures.

## Docker verification

- Run `docker compose config` before building.
- Run `docker build --tag eztalk-api:test .` after Dockerfile changes.
- If the Docker daemon is unavailable, report that limitation separately; do not treat it as an application-test failure.
- Keep test-only packages out of the runtime image unless runtime code imports them.

## Failure handling

- Distinguish application failures from test-harness, terminal-encoding, network, and Docker-daemon failures.
- Record repeated application defects in `skills/maintain-fastapi-chat/references/bug-patterns.md`.
- Do not weaken assertions to make a failing behavior pass.
