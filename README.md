# EZTalk Backend

Production-grade FastAPI backend for an English-Vietnamese conversation practice app. The service supports real-time WebSocket chat, OpenAI-compatible vLLM streaming, persistent conversation history, and AI-powered conversation evaluation.

## Architecture Overview

EZTalk is designed for horizontal scale-out. API containers are stateless at the process level; shared state is moved to Postgres and Redis.

```txt
Mobile/Web Client
   │
   │ WebSocket /ws/chat/{session_id}?api_key=...
   │ HTTP      /api/v1/sessions/{session_id}/...
   ▼
Load Balancer / Ingress
   │
   ├───────────────┬───────────────┬───────────────┐
   ▼               ▼               ▼               │
FastAPI API #1  FastAPI API #2  FastAPI API #3      │
Gunicorn        Gunicorn        Gunicorn            │
UvicornWorker   UvicornWorker   UvicornWorker       │
   │               │               │
   ├───────────────┴──────┬────────┘
   │                      │
   ▼                      ▼
Redis Pub/Sub         PgBouncer
WebSocket event       Transaction pool
fan-out               │
                      ▼
                   Postgres
                   Users / Sessions / Messages

FastAPI API containers
   │
   ▼
vLLM OpenAI-compatible API
/v1/chat/completions
```

Core runtime components:

- FastAPI: HTTP API and WebSocket server.
- Gunicorn: production process manager.
- UvicornWorker: async ASGI worker for FastAPI/WebSockets.
- Redis Pub/Sub: synchronizes WebSocket session events across multiple API replicas.
- PgBouncer: transaction-level connection pooling in front of Postgres.
- Postgres: durable storage for users, sessions, and messages.
- vLLM: OpenAI-compatible inference server for chat and evaluation.

Production API command:

```txt
gunicorn app.main:app -w <auto> -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080 --keep-alive 65
```

The Docker entrypoint computes workers automatically:

```txt
workers = 2 * CPU cores + 1
```

Override with:

```txt
WEB_CONCURRENCY=4
```

## WebSocket JSON Protocol Reference

### Connection URL

```txt
ws://<host>/ws/chat/{session_id}?api_key=<api_key>
wss://<host>/ws/chat/{session_id}?api_key=<api_key>
```

Authentication is currently API-key based. The frontend must pass `api_key` as a query parameter. The backend resolves the real `user_id` from the `users` table.

Do not send `user_id` from the client. It is ignored by the new production auth flow.

### Client → Server Message

The client sends plain text frames:

```txt
Hello, I want to practice small talk.
```

### Server → Client Events

All server responses are JSON events.

#### `connected`

Sent once after the socket is accepted and the `api_key` is valid.

```json
{
  "type": "connected",
  "session_id": "session_123",
  "user_id": "user_abc",
  "message": "WebSocket connected."
}
```

#### `assistant_delta`

Streaming chunk from the AI assistant. The frontend should append `delta` to the current assistant bubble.

```json
{
  "type": "assistant_delta",
  "session_id": "session_123",
  "delta": "That sounds fun! "
}
```

#### `assistant_done`

Marks the end of the assistant response. The `message` field contains the full assistant answer.

```json
{
  "type": "assistant_done",
  "session_id": "session_123",
  "message": "That sounds fun! What kind of topics do you want to practice?"
}
```

#### `error`

Recoverable error event. The frontend should display `message` and decide whether to keep or close the socket based on `code`.

```json
{
  "type": "error",
  "session_id": "session_123",
  "code": "auth_error",
  "message": "API key không hợp lệ hoặc đã hết hạn."
}
```

Current error codes:

| Code | Meaning | Suggested client behavior |
|---|---|---|
| `auth_error` | API key invalid, expired, or session ownership denied. | Stop chat flow, ask user to re-authenticate. |
| `empty_message` | User sent blank text. | Keep socket open, ask user to type a message. |
| `llm_unavailable` | vLLM did not respond or returned an upstream error. | Keep socket open, allow retry. |
| `database_error` | Message pair could not be saved. | Warn user that the conversation was not persisted. |

### Frontend Integration Notes

- Treat `assistant_delta` as a streaming append operation.
- Treat `assistant_done` as the response boundary.
- Do not render `assistant_done.message` twice if the UI already assembled all deltas.
- When Redis broadcast is enabled, events are published through the shared session channel so multiple API replicas can coordinate WebSocket state.
- The backend stores the user message and assistant response atomically in one database transaction after the assistant response is generated.

## Evaluation Schema

Endpoint:

```txt
POST /api/v1/sessions/{session_id}/evaluate?api_key=<api_key>
```

The backend loads the full transcript for the authenticated user/session and calls vLLM with:

```json
{
  "response_format": {
    "type": "json_object"
  }
}
```

The result is validated by Pydantic before being returned to the client.

### JSON Output

```json
{
  "grammar_score": 72,
  "vocabulary_score": 68,
  "eq_score": 81,
  "cefr_level": "A2",
  "grammar_errors": [
    {
      "original": "I go to school yesterday.",
      "corrected": "I went to school yesterday.",
      "explanation_vi": "Khi nói về hôm qua, cần dùng thì quá khứ."
    }
  ],
  "suggested_replies": [
    "I went there to meet my classmates.",
    "It was fun, but I felt a little tired."
  ],
  "overall_feedback_vi": "Bạn giao tiếp rõ ý và nên chú ý thì quá khứ."
}
```

### Field Contract

| Field | Type | Range / Values | Mobile usage |
|---|---|---|---|
| `grammar_score` | integer | `0` to `100` | Radar chart axis: Grammar |
| `vocabulary_score` | integer | `0` to `100` | Radar chart axis: Vocabulary |
| `eq_score` | integer | `0` to `100` | Radar chart axis: EQ / Conversation Flow |
| `cefr_level` | string | `A1`, `A2`, `B1`, `B2`, `C1`, `C2` | Level badge |
| `grammar_errors` | array | list of correction objects | Feedback list |
| `grammar_errors[].original` | string | original user text | Show before correction |
| `grammar_errors[].corrected` | string | corrected version | Show corrected sentence |
| `grammar_errors[].explanation_vi` | string | Vietnamese explanation | Learner explanation |
| `suggested_replies` | array of strings | suggested natural replies | Practice suggestions |
| `overall_feedback_vi` | string | Vietnamese feedback summary | Summary card |

### Radar Chart Mapping

Use these three values directly as percentage axes:

```json
[
  { "label": "Grammar", "value": 72 },
  { "label": "Vocabulary", "value": 68 },
  { "label": "EQ", "value": 81 }
]
```

## Production Deployment Guide

Production compose file:

```txt
docker-compose.prod.yml
```

Required command:

```bash
docker compose -f docker-compose.prod.yml up --build --scale api=3 -d
```

This starts:

- `api`: scalable FastAPI/Gunicorn service.
- `migrate`: one-shot DB initialization job.
- `redis`: Redis 7 Alpine for Pub/Sub.
- `postgres`: Postgres 16 Alpine.
- `pgbouncer`: connection pooler in front of Postgres.

The `api` service uses `expose: 8080` instead of binding a fixed host port. This avoids port collisions when scaling multiple API replicas. In production, place a load balancer, ingress, Nginx, Traefik, or cloud service router in front of the API replicas.

### Required Secret Manager Variables

These must be injected by CI/CD, platform environment variables, Docker secrets, or a secret manager. Do not hardcode them in compose files.

| Variable | Required | Description |
|---|---:|---|
| `POSTGRES_USER` | yes | Postgres application username. |
| `POSTGRES_PASSWORD` | yes | Postgres password. Must come from Secret Manager. |
| `POSTGRES_DB` | yes | Postgres database name. |
| `VLLM_BASE_URL` | yes | OpenAI-compatible vLLM base URL, for example `http://vllm:8000/v1`. |
| `VLLM_MODEL` | yes | Served model name exposed by vLLM. |
| `VLLM_API_KEY` | no | Required only if vLLM was started with API-key protection. |
| `IMAGE_TAG` | no | Docker image tag. Defaults to `latest`. |
| `WEB_CONCURRENCY` | no | Override Gunicorn worker count. Defaults to `2 * CPU + 1`. |
| `GUNICORN_KEEP_ALIVE` | no | Keep-alive seconds. Defaults to `65`. |
| `DB_POOL_SIZE` | no | SQLAlchemy pool size per API worker. Defaults to `5`. |
| `DB_MAX_OVERFLOW` | no | SQLAlchemy overflow connections per worker. Defaults to `10`. |
| `PGBOUNCER_MAX_CLIENT_CONN` | no | PgBouncer max client connections. Defaults to `1000`. |
| `PGBOUNCER_DEFAULT_POOL_SIZE` | no | PgBouncer default server pool size. Defaults to `50`. |
| `PGBOUNCER_RESERVE_POOL_SIZE` | no | PgBouncer reserve pool size. Defaults to `10`. |

### Example Production Startup

PowerShell:

```powershell
$env:POSTGRES_USER="eztalk"
$env:POSTGRES_PASSWORD="<load-from-secret-manager>"
$env:POSTGRES_DB="eztalk"
$env:VLLM_BASE_URL="http://vllm:8000/v1"
$env:VLLM_MODEL="your-served-model-name"
$env:VLLM_API_KEY="<optional>"

docker compose -f docker-compose.prod.yml up --build --scale api=3 -d
```

Bash:

```bash
export POSTGRES_USER="eztalk"
export POSTGRES_PASSWORD="<load-from-secret-manager>"
export POSTGRES_DB="eztalk"
export VLLM_BASE_URL="http://vllm:8000/v1"
export VLLM_MODEL="your-served-model-name"
export VLLM_API_KEY="<optional>"

docker compose -f docker-compose.prod.yml up --build --scale api=3 -d
```

### Production Readiness Notes

- The current `migrate` service calls SQLAlchemy `init_db()`. This is acceptable for the current schema bootstrap, but the next production-hardening step should replace it with Alembic migrations.
- API replicas do not run DB initialization on startup in production:

```txt
RUN_DB_INIT_ON_STARTUP=false
```

- Redis Pub/Sub is enabled in production:

```txt
ENABLE_REDIS_BROADCAST=true
```

- PgBouncer uses transaction pooling:

```txt
PGBOUNCER_POOL_MODE=transaction
```

- Postgres tuning is stored in:

```txt
infra/postgres/postgres.conf
```

### Local Quality Gate

Run before pushing:

```bash
python -m ruff check .
python -m pytest -q
docker compose config --quiet
docker compose -f docker-compose.prod.yml config --quiet
```
